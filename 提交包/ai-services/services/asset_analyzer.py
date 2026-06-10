from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from config import Settings
from models.repository import SQLiteRepository
from services.vision import analyze_frames
from services.scene_classifier import SceneClassifier


class AssetValidationError(ValueError):
    pass


class AssetProjectNotFoundError(LookupError):
    pass


SUPPORTED_TYPES = {
    "image": ("image/",),
    "video": ("video/",),
    "text": ("text/plain",),
}

MAX_ASSET_BYTES = 50 * 1024 * 1024  # 50MB per asset


def classify_asset_type(content_type: str | None) -> str:
    normalized = (content_type or "").lower()
    if normalized.startswith("image/"):
        return "image"
    if normalized.startswith("video/"):
        return "video"
    if normalized.startswith("text/plain"):
        return "text"
    raise AssetValidationError("Unsupported asset file type")


def safe_filename(filename: str | None) -> str:
    raw = filename or "asset"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(raw).name).strip("._")
    return safe or "asset"


class AssetAnalyzer:
    def __init__(self, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def analyze_upload(self, project_id: str, file: UploadFile, content: bytes) -> dict[str, Any]:
        asset_type = classify_asset_type(file.content_type)
        if not content:
            raise AssetValidationError("Asset file is empty")
        if len(content) > MAX_ASSET_BYTES:
            raise AssetValidationError(f"Asset file exceeds {MAX_ASSET_BYTES // (1024*1024)}MB limit")
        if self.repository.get_project(project_id) is None:
            raise AssetProjectNotFoundError(f"Project not found: {project_id}")

        stored_path = self._save_file(project_id, file.filename, content)
        analysis = self._analyze_file(asset_type, stored_path, content)
        tag = _primary_tag(analysis, stored_path.name, asset_type)
        return self.repository.create_asset(
            project_id=project_id,
            name=file.filename or stored_path.name,
            asset_type=asset_type,
            file_path=str(stored_path),
            tag=tag,
            analysis=analysis,
        )

    def _save_file(self, project_id: str, filename: str | None, content: bytes) -> Path:
        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{uuid4().hex}_{safe_filename(filename)}"
        output_path.write_bytes(content)
        return output_path

    def _analyze_file(self, asset_type: str, stored_path: Path, content: bytes) -> dict[str, Any]:
        if asset_type == "text":
            result = _analyze_text(content, stored_path.name)
        elif asset_type == "image":
            result = _analyze_image(stored_path, self.settings)
        else:
            result = _analyze_video(stored_path, self.settings)

        # Classify scene type (uses LLM when available, keyword fallback otherwise).
        classifier = SceneClassifier(
            llm_endpoint=self.settings.doubao_llm_endpoint,
            llm_api_key=self.settings.doubao_llm_api_key,
            llm_model=self.settings.doubao_llm_model,
        )
        scene_type = classifier.classify(result)
        if scene_type:
            result["scene_type"] = scene_type
            existing_tags = [str(t) for t in result.get("tags", [])]
            tag_map = {"hook": "冲突画面", "pain": "痛点场景", "product": "产品特写", "proof": "演示证明", "cta": "优惠购买"}
            scene_tag = tag_map.get(scene_type, "")
            if scene_tag and scene_tag not in existing_tags:
                existing_tags.append(scene_tag)
            result["tags"] = existing_tags
        return result


def _analyze_image(path: Path, settings: Settings) -> dict[str, Any]:
    vision = analyze_frames([path], settings)
    frame = (vision.get("frames") or [{}])[0]
    description = _description_from_name(path.name, frame.get("description"))
    ocr_text = " ".join(frame.get("ocr") or [])
    search_text = " ".join([path.name, description, ocr_text, *[str(tag) for tag in frame.get("tags") or []]])
    return {
        "asset_status": "analyzed",
        "analysis_type": "image",
        "description": description,
        "tags": _tags_from_text(search_text, frame.get("tags") or []),
        "ocr_text": ocr_text,
        "vision_status": vision.get("vision_status", "completed"),
    }


def _analyze_video(path: Path, settings: Settings) -> dict[str, Any]:
    frame_path = _extract_video_preview(path, settings)
    if frame_path and frame_path.exists():
        analysis = _analyze_image(frame_path, settings)
        analysis["analysis_type"] = "video"
        analysis["representative_frame"] = str(frame_path)
        return analysis
    tags = _tags_from_text(path.name, [])
    return {
        "asset_status": "fallback",
        "analysis_type": "video",
        "description": _description_from_name(path.name, None),
        "tags": tags,
        "ocr_text": "",
        "vision_status": "skipped",
    }


def _extract_video_preview(path: Path, settings: Settings) -> Path | None:
    ffmpeg = shutil.which(settings.ffmpeg_path) or (settings.ffmpeg_path if Path(settings.ffmpeg_path).exists() else None)
    if not ffmpeg:
        return None
    output = path.with_suffix(".preview.jpg")
    completed = subprocess.run(
        [ffmpeg, "-y", "-ss", "0.5", "-i", str(path), "-frames:v", "1", "-q:v", "2", str(output)],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return output if completed.returncode == 0 and output.exists() else None


def _analyze_text(content: bytes, filename: str) -> dict[str, Any]:
    text = content.decode("utf-8", errors="replace").strip()
    tags = _tags_from_text(f"{filename} {text}", [])
    return {
        "asset_status": "analyzed",
        "analysis_type": "text",
        "description": text[:160] or filename,
        "tags": tags or ["文案"],
        "ocr_text": text,
    }


def _description_from_name(filename: str, fallback: str | None) -> str:
    if fallback and fallback != "Key product or scene frame awaiting visual model analysis":
        return fallback
    mapped = [tag for tag in _tags_from_text(filename, []) if tag != "素材"]
    if mapped:
        return "、".join(mapped)
    return fallback or f"{filename} 素材"


def _tags_from_text(text: str, existing: list[Any]) -> list[str]:
    haystack = text.lower()
    tags = [str(tag) for tag in existing if str(tag)]
    keyword_map = {
        "冲突画面": ["conflict", "hook", "悬念", "冲突", "问题", "对比"],
        "产品特写": ["product", "close", "demo", "产品", "特写", "功能", "包装"],
        "痛点场景": ["pain", "scene", "office", "commute", "困境", "场景", "人物", "情绪"],
        "优惠购买": ["offer", "price", "cta", "buy", "logo", "优惠", "价格", "购买", "行动"],
        "演示证明": ["proof", "test", "data", "review", "演示", "数据", "证言"],
    }
    for tag, needles in keyword_map.items():
        if any(needle.lower() in haystack for needle in needles) and tag not in tags:
            tags.append(tag)
    return tags or ["素材"]


def _primary_tag(analysis: dict[str, Any], filename: str, asset_type: str) -> str:
    tags = [str(tag) for tag in analysis.get("tags", []) if str(tag)]
    if tags:
        return tags[0]
    return {"image": "图片素材", "video": "视频素材", "text": "文案素材"}[asset_type]
