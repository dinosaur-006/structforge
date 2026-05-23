from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

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
        self.detector = GapDetector(repository)
        self.editor = StructureEditor(repository)
        self.matcher = AssetMatcher(repository)

    def fix(self, project_id: str, gap_id: str, strategy: str) -> dict[str, Any]:
        if strategy not in STRATEGY_ORDER:
            raise GapFixError(f"Invalid strategy: {strategy}")
        gap = self.detector.get_gap(project_id, gap_id)
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
            for strategy in STRATEGY_ORDER:
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
            if self._can_reorder(project_id):
                return self.editor.get_structure(project_id)
            return self._apply_packaging(project_id, gap)
        if strategy == "packaging":
            return self._apply_packaging(project_id, gap)
        if strategy == "aigc":
            return self._apply_packaging(project_id, gap)
        if strategy == "recompose":
            return self._apply_recompose(project_id, gap) or self._apply_packaging(project_id, gap)
        raise GapFixError(f"Invalid strategy: {strategy}")

    def _can_reorder(self, project_id: str) -> bool:
        return any(asset["match_score"] >= 60 for asset in self.repository.list_assets(project_id))

    def _apply_packaging(self, project_id: str, gap: dict[str, Any]) -> VideoStructure:
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == gap["segmentId"]), None)
        if segment is None:
            raise GapNotFoundError(f"Gap not found: {gap['id']}")

        asset_dir = self.settings.upload_dir / project_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = asset_dir / f"{gap['id']}_packaging.svg"
        output_path.write_text(_svg_for_gap(segment.label, gap["requiredSlot"]), encoding="utf-8")
        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} 包装补全.svg",
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
        output_path = asset_dir / f"{gap['id']}_recompose{source.suffix or '.mp4'}"
        shutil.copyfile(source, output_path)
        structure = self.editor.get_structure(project_id)
        segment = next((item for item in structure.script if item.id == segment_id), None)
        if segment is None:
            return None
        tag = _tag_for_segment_type(segment.type)
        asset = self.repository.create_asset(
            project_id=project_id,
            name=f"{segment.label} 素材重组{output_path.suffix}",
            asset_type="video",
            file_path=str(output_path),
            tag=f"{tag} 素材重组",
            analysis={"description": f"{segment.label} 素材重组 {tag}", "tags": [tag, "素材重组"], "ocr_text": ""},
        )
        self.repository.update_asset_match(asset["id"], score=88.0, status="matched")
        return self.editor.update_segment(project_id, segment.id, {"assetId": asset["id"]})


def _tag_for_segment_type(segment_type: str) -> str:
    return {
        "hook": "冲突画面",
        "pain": "痛点场景",
        "product": "产品特写",
        "proof": "演示证明",
        "cta": "优惠购买",
    }.get(segment_type, "包装补全")


def _svg_for_gap(label: str, required_slot: str) -> str:
    safe_label = html.escape(label)
    safe_slot = html.escape(required_slot)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
        '<rect width="1080" height="1920" fill="#F5F4F0"/>'
        '<rect x="96" y="736" width="888" height="448" rx="32" fill="#FFFFFF" stroke="#E7E5E0" stroke-width="4"/>'
        f'<text x="540" y="910" text-anchor="middle" font-size="72" font-family="Arial" fill="#1A1A18">{safe_label}</text>'
        f'<text x="540" y="1018" text-anchor="middle" font-size="40" font-family="Arial" fill="#6B6B65">{safe_slot}</text>'
        '<text x="540" y="1120" text-anchor="middle" font-size="34" font-family="Arial" fill="#5C8B67">StructForge Packaging Fill</text>'
        "</svg>"
    )
