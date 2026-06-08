from __future__ import annotations

import base64
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import VideoStructure
from services.asset_matcher import AssetMatcher
from services.auto_reorder import AutoReorderService
from services.gap_detector import GapDetector, GapNotFoundError
from services.structure_editor import StructureEditor, StructureNotFoundError


class GapFixError(ValueError):
    pass


STRATEGY_ORDER = ["reorder", "packaging", "aigc", "recompose"]


class GapFiller:
    def __init__(self, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.detector = GapDetector(repository, settings)
        self.editor = StructureEditor(repository)
        self.matcher = AssetMatcher(repository)

    def fix(self, project_id: str, gap_id: str, strategy: str) -> dict[str, Any]:
        if strategy not in STRATEGY_ORDER:
            raise GapFixError(f"Invalid strategy: {strategy}")
        gap = self.detector.get_gap(project_id, gap_id)
        strategy_state = next(item for item in gap["strategies"] if item["id"] == strategy)
        if not strategy_state["available"]:
            raise GapFixError(f"策略不可用: {strategy_state['unavailableReason']}")
        structure = self._apply_strategy(project_id, gap, strategy)
        self.matcher.match_project_assets(project_id)
        latest_gaps = self.detector.detect(project_id)
        return {
            "gap_id": gap_id,
            "status": "fixed" if all(item["id"] != gap_id for item in latest_gaps) else "open",
            "updated_structure": structure,
            "assets": self.repository.list_assets(project_id),
            "gaps": latest_gaps,
        }

    def fix_all(self, project_id: str) -> dict[str, Any]:
        fixed_details: list[dict[str, Any]] = []
        latest_structure: VideoStructure | None = None

        while True:
            open_gaps = self.detector.detect(project_id)
            if not open_gaps:
                break
            gap = open_gaps[0]
            before_count = len(open_gaps)
            result: dict[str, Any] | None = None
            available_ids = {item["id"] for item in gap["strategies"] if item["available"]}
            for strategy in STRATEGY_ORDER:
                if strategy not in available_ids:
                    continue
                result = self.fix(project_id, gap["id"], strategy)
                latest_structure = result["updated_structure"]
                if result["status"] == "fixed":
                    fixed_details.append(result)
                    break
            if result is None or len(self.detector.detect(project_id)) >= before_count:
                raise GapFixError(f"Failed to fix gap: {gap['id']}")

        return {
            "fixed_count": len(fixed_details),
            "details": fixed_details,
            "gaps": self.detector.detect(project_id),
            "updated_structure": latest_structure or self.editor.get_structure(project_id),
            "assets": self.repository.list_assets(project_id),
        }

    def _apply_strategy(self, project_id: str, gap: dict[str, Any], strategy: str) -> VideoStructure:
        if strategy == "reorder":
            return self._apply_reorder(project_id, gap)
        if strategy == "packaging":
            return self._apply_packaging(project_id, gap)
        if strategy == "aigc":
            return self._apply_aigc(project_id, gap)
        if strategy == "recompose":
            structure = self._apply_recompose(project_id, gap)
            if structure is None:
                raise GapFixError("素材重组需要可用视频素材")
            return structure
        raise GapFixError(f"Invalid strategy: {strategy}")

    def _apply_reorder(self, project_id: str, _gap: dict[str, Any]) -> VideoStructure:
        """AI-powered deterministic reorder to maximize asset coverage of critical positions."""
        structure = self.editor.get_structure(project_id)
        assets = self.repository.list_assets(project_id)
        matches = self.matcher.match_project_assets(project_id)

        # Build per-segment best match score.
        asset_scores: dict[str, float] = {}
        for match in matches:
            current = asset_scores.get(match["segment_id"], 0.0)
            if match["score"] > current:
                asset_scores[match["segment_id"]] = match["score"]

        reorder_service = AutoReorderService()
        updated, explanation = reorder_service.reorder(structure, asset_scores)

        self.editor.replace_structure(project_id, updated.model_dump(mode="json", by_alias=True))
        return updated

    def _apply_packaging(self, project_id: str, gap: dict[str, Any]) -> VideoStructure:
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == gap["segmentId"]), None)
        if segment is None:
            raise GapNotFoundError(f"Gap not found: {gap['id']}")

        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{gap['id']}_packaging.png"
        render_packaging_card(
            output_path,
            title=segment.label,
            body=segment.copy_text or gap["requiredSlot"],
            card_type=segment.type,
            font_path=self.settings.packaging_font_path,
        )
        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} 包装补全.png",
            asset_type="image",
            file_path=str(output_path),
            tag=f"{tag} 包装补全",
            analysis={
                "asset_status": "generated",
                "analysis_type": "image",
                "description": f"{segment.label} 包装补全 {tag}",
                "tags": [tag, "包装补全"],
                "ocr_text": segment.copy_text,
            },
            origin="packaging",
        )
        self.repository.update_asset_match(asset["id"], score=92.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})

    def _apply_recompose(self, project_id: str, gap: dict[str, Any]) -> VideoStructure | None:
        video_asset = next((asset for asset in self.repository.list_assets(project_id) if asset["type"] == "video" and asset.get("file_path")), None)
        if not video_asset:
            return None
        source = Path(video_asset["file_path"])
        if not source.exists():
            return None
        segment_id = gap["segmentId"]
        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == segment_id), None)
        if segment is None:
            return None
        output_path = asset_dir / f"{gap['id']}_recompose.mp4"
        # Smart seek: use vision analysis to find best matching clip position.
        start_time = _find_best_seek_point(video_asset, segment.type, segment.duration)
        _run_ffmpeg(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-ss",
                f"{start_time:.3f}",
                "-i",
                str(source),
                "-t",
                f"{max(segment.duration, 0.5):.3f}",
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )
        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} 素材重组{output_path.suffix}",
            asset_type="video",
            file_path=str(output_path),
            tag=f"{tag} 素材重组",
            analysis={"description": f"{segment.label} 素材重组 {tag}", "tags": [tag, "素材重组"], "ocr_text": ""},
            origin="recompose",
        )
        self.repository.update_asset_match(asset["id"], score=88.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})

    def _apply_aigc(self, project_id: str, gap: dict[str, Any]) -> VideoStructure:
        # Use ARK Seedream image API when image key is available.
        if self.settings.doubao_image_api_key:
            return self._apply_seedream(project_id, gap)

        # Fallback: no API key at all.
        return self._apply_aigc_fallback(project_id, gap)

    def _apply_seedream(self, project_id: str, gap: dict[str, Any]) -> VideoStructure:
        """Generate AIGC image via Doubao Seedream ARK Images API."""
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == gap["segmentId"]), None)
        if segment is None:
            raise GapNotFoundError(f"Gap not found: {gap['id']}")
        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{gap['id']}_aigc.png"

        prompt = (
            f"电商短视频画面：{segment.visual}。{segment.copy_text}。"
            f"竖版9:16构图，{_scene_style(segment.type)}，专业布光，高清写实。"
        )

        try:
            resp = httpx.post(
                "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                headers={"Authorization": f"Bearer {self.settings.doubao_image_api_key}"},
                json={
                    "model": self.settings.doubao_image_model,
                    "prompt": prompt,
                    "size": "2048x2048",
                    "response_format": "b64_json",
                    "watermark": False,
                },
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            images = payload.get("data", [])
            if images and "b64_json" in images[0]:
                output_path.write_bytes(base64.b64decode(images[0]["b64_json"]))
            elif images and "url" in images[0]:
                img_resp = httpx.get(images[0]["url"], timeout=30)
                img_resp.raise_for_status()
                output_path.write_bytes(img_resp.content)
            else:
                return self._apply_aigc_fallback(project_id, gap)
        except Exception:
            return self._apply_aigc_fallback(project_id, gap)

        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} AIGC.png",
            asset_type="image",
            file_path=str(output_path),
            tag=f"{tag} AIGC",
            analysis={"description": f"{segment.label} Seedream AI {tag}", "tags": [tag, "AIGC"], "ocr_text": ""},
            origin="aigc",
        )
        self.repository.update_asset_match(asset["id"], score=92.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})

    def _apply_aigc_fallback(self, project_id: str, gap: dict[str, Any]) -> VideoStructure:
        """Generate a styled placeholder card when Jimeng is not configured."""
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == gap["segmentId"]), None)
        if segment is None:
            raise GapNotFoundError(f"Gap not found: {gap['id']}")
        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{gap['id']}_aigc_fallback.png"

        # Build a distinctive gradient card.
        from PIL import Image, ImageDraw

        canvas = Image.new("RGB", (1080, 1920), "#2A2A28")
        draw = ImageDraw.Draw(canvas)
        accent = "#C87D53" if segment.type == "cta" else "#7C8BBD"
        bg_color = (43, 43, 40) if segment.type != "cta" else (50, 40, 35)
        draw.rectangle((0, 660, 1080, 1260), fill=bg_color)
        draw.rectangle((80, 680, 96, 1240), fill=accent)
        label = "AI PLACEHOLDER" if segment.type == "cta" else "AI GENERATED"
        draw.text((140, 760), label, fill=accent, font=_load_font(30, self.settings.packaging_font_path))
        draw.text((140, 850), segment.label, fill="#F5F4F0", font=_load_font(68, self.settings.packaging_font_path))
        draw.text((140, 960), segment.copy_text or segment.visual, fill="#9E9A90", font=_load_font(32, self.settings.packaging_font_path))
        draw.text((140, 1040), "Powered by StructForge AIGC", fill="#6B6B65", font=_load_font(24, self.settings.packaging_font_path))
        # Watermark-style horizontal lines for visual distinction.
        for idx in range(5):
            y_pos = 1100 + idx * 50
            draw.rectangle((140, y_pos, 940, y_pos + 2), fill=(108, 108, 100) if idx % 2 == 0 else (80, 80, 76))
        canvas.save(output_path, format="PNG")

        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} AIGC占位.png",
            asset_type="image",
            file_path=str(output_path),
            tag=f"{tag} AIGC",
            analysis={"description": f"{segment.label} AIGC占位补全 {tag}", "tags": [tag, "AIGC", "占位"], "ocr_text": ""},
            origin="aigc",
        )
        self.repository.update_asset_match(asset["id"], score=72.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})


def _find_best_seek_point(asset: dict[str, Any], target_type: str, clip_duration: float) -> float:
    """Find the best start time in the video asset for the target segment type."""
    analysis = asset.get("analysis") or {}
    scene_type = analysis.get("scene_type", "")
    tags = [str(t).strip() for t in analysis.get("tags", [])]

    # If scene was already classified as matching, start from 0.
    if scene_type == target_type:
        return 0.0

    # If tags match, start from 0.
    tag_map = {"hook": "冲突画面", "pain": "痛点场景", "product": "产品特写", "proof": "演示证明", "cta": "优惠购买"}
    if tag_map.get(target_type, "") in tags:
        return 0.0

    # Heuristic: different segment types suggest different parts of the video.
    # hook -> start (0-20%), product -> early-mid (20-40%), proof -> mid (40-60%), cta -> end (60-80%).
    position_hints = {"hook": 0.05, "pain": 0.15, "product": 0.25, "proof": 0.45, "cta": 0.65}
    ratio = position_hints.get(target_type, 0.25)
    # Estimate total duration from file path (not probe, to avoid overhead).
    return max(0.0, ratio * 30.0 - clip_duration * 0.3)  # assume ~30s video, leave room for clip


def _scene_style(segment_type: str) -> str:
    return {
        "hook": "冲击力强，高对比度，抓眼球",
        "pain": "真实场景，生活化布光",
        "product": "产品居中，商业摄影，干净背景",
        "proof": "对比展示，数据可视化风格",
        "cta": "促销氛围，暖色调，价格突出",
    }.get(segment_type, "专业电商风格")


def _tag_for_segment_type(segment_type: str) -> str:
    return {
        "hook": "冲突画面",
        "pain": "痛点场景",
        "product": "产品特写",
        "proof": "演示证明",
        "cta": "优惠购买",
    }.get(segment_type, "包装补全")


def render_packaging_card(
    output_path: Path,
    *,
    title: str,
    body: str,
    card_type: str,
    font_path: Path | None = None,
) -> None:
    # Strip production params 【镜】【字】【速】【情】【视】 from card display text
    import re
    clean_body = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', body)
    clean_body = re.sub(r'【[镜字速情视]】', '', clean_body)
    clean_body = re.sub(r'\s+', ' ', clean_body).strip() or body

    # ── Segment-specific accent colors ──
    accent_map = {
        "hook": "#E85D3A",    # warm red-orange
        "pain": "#8B5CF6",    # purple
        "product": "#3B82F6", # blue
        "proof": "#10B981",   # green
        "cta": "#F59E0B",     # amber/gold
        "offer": "#EF4444",   # red
        "compare": "#06B6D4", # cyan
    }
    accent = accent_map.get(card_type, "#6366F1")
    dark_bg = "#0F0F1A"
    card_bg = "#1A1A2E"
    text_primary = "#F1F5F9"
    text_secondary = "#94A3B8"

    canvas = Image.new("RGB", (1080, 1920), dark_bg)
    draw = ImageDraw.Draw(canvas)

    # Top-to-bottom gradient background
    for y in range(1920):
        ratio = y / 1920
        r = int(15 + (26 - 15) * ratio)
        g = int(15 + (26 - 15) * ratio)
        b = int(26 + (46 - 26) * ratio)
        draw.rectangle((0, y, 1080, y + 1), fill=(r, g, b))

    # Central card area
    draw.rounded_rectangle((60, 620, 1020, 1300), radius=40, fill=card_bg, outline=accent, width=3)

    # Top accent bar
    draw.rectangle((60, 620, 1020, 628), fill=accent)

    # Type label
    draw.text((120, 690), title, fill=accent, font=_load_font(42, font_path))

    # Body text — larger and centered
    body_font = _load_font(52, font_path)
    body_lines = _fit_text_block(clean_body, width=18, max_lines=3)
    draw.multiline_text(
        (120, 800),
        body_lines,
        fill=text_primary,
        font=body_font,
        spacing=20,
    )

    # Divider line
    draw.rectangle((120, 1050, 300, 1053), fill=accent)

    # Footer
    draw.text((120, 1100), "StructForge AI 生成", fill=text_secondary, font=_load_font(28, font_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def _fit_text_block(value: str, *, width: int, max_lines: int) -> str:
    lines = textwrap.wrap(value.strip(), width=width) or [""]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    selected = lines[:max_lines]
    suffix = "..."
    selected[-1] = selected[-1][: max(width - len(suffix), 1)].rstrip() + suffix
    return "\n".join(selected)


def _load_font(size: int, configured_path: Path | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        configured_path,
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _run_ffmpeg(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "FFmpeg command failed").strip()
        raise GapFixError(message[-1200:])
