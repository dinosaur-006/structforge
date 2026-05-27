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
            raise GapFixError("结构重排仅支持人工时间线编辑")
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
        _run_ffmpeg(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-ss",
                "0",
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
        if not self.settings.jimeng_image_endpoint or not self.settings.jimeng_image_api_key:
            raise GapFixError("策略不可用: 未配置即梦 API")
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == gap["segmentId"]), None)
        if segment is None:
            raise GapNotFoundError(f"Gap not found: {gap['id']}")
        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{gap['id']}_aigc.png"
        response = httpx.post(
            self.settings.jimeng_image_endpoint,
            headers={"Authorization": f"Bearer {self.settings.jimeng_image_api_key}"},
            json={"prompt": f"{segment.visual}; {segment.copy_text}", "size": "1080x1920"},
            timeout=60,
        )
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("image/"):
            output_path.write_bytes(response.content)
        else:
            payload = response.json()
            encoded = payload.get("image_base64") or (payload.get("data") or [{}])[0].get("b64_json")
            image_url = payload.get("image_url") or (payload.get("data") or [{}])[0].get("url")
            if encoded:
                output_path.write_bytes(base64.b64decode(encoded))
            elif image_url:
                image_response = httpx.get(image_url, timeout=60)
                image_response.raise_for_status()
                output_path.write_bytes(image_response.content)
            else:
                raise GapFixError("即梦 API 未返回图片内容")
        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} AIGC.png",
            asset_type="image",
            file_path=str(output_path),
            tag=f"{tag} AIGC",
            analysis={"description": f"{segment.label} AIGC {tag}", "tags": [tag, "AIGC"], "ocr_text": ""},
            origin="aigc",
        )
        self.repository.update_asset_match(asset["id"], score=92.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})


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
    canvas = Image.new("RGB", (1080, 1920), "#F5F4F0")
    draw = ImageDraw.Draw(canvas)
    accent = "#C87D53" if card_type == "cta" else "#5C8B67"
    draw.rectangle((0, 0, 1080, 1920), fill="#F5F4F0")
    draw.rounded_rectangle((82, 690, 998, 1230), radius=34, fill="#FFFFFF", outline="#E7E5E0", width=4)
    draw.rectangle((82, 690, 94, 1230), fill=accent)
    label = "LIMITED OFFER" if card_type == "cta" else "STRUCTURE FILL"
    draw.text((134, 765), label, fill=accent, font=_load_font(30, font_path))
    draw.multiline_text(
        (134, 850),
        _fit_text_block(title, width=12, max_lines=2),
        fill="#1A1A18",
        font=_load_font(76, font_path),
        spacing=16,
    )
    draw.multiline_text(
        (134, 1040),
        _fit_text_block(body, width=20, max_lines=2),
        fill="#6B6B65",
        font=_load_font(38, font_path),
        spacing=12,
    )
    draw.text((134, 1180), "StructForge", fill="#1A1A18", font=_load_font(28, font_path))
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
