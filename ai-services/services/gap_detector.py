from __future__ import annotations

from typing import Any

from models.repository import SQLiteRepository
from models.schemas import ScriptSegment
from services.asset_matcher import AssetMatcher
from services.structure_editor import StructureEditor, StructureNotFoundError


MATCH_THRESHOLD = 60.0

STRATEGIES = [
    {
        "id": "reorder",
        "name": "结构重排",
        "description": "调整分镜顺序，优先把已有素材覆盖关键位置。",
    },
    {
        "id": "packaging",
        "name": "包装补全",
        "description": "生成标题卡、价格卡或信息包装图填补空槽。",
    },
    {
        "id": "aigc",
        "name": "AIGC 生成",
        "description": "使用生成式图片补足缺失画面；未配置时自动降级。",
    },
    {
        "id": "recompose",
        "name": "素材重组",
        "description": "复用现有视频素材进行裁切或重组；不可用时自动降级。",
    },
]


class GapDetector:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.editor = StructureEditor(repository)
        self.matcher = AssetMatcher(repository)

    def detect(self, project_id: str) -> list[dict[str, Any]]:
        structure = self.editor.get_structure(project_id)
        assets = self.repository.list_assets(project_id)
        matches = self.matcher.match_project_assets(project_id)
        matched_segment_ids = {
            match["segment_id"]
            for match in matches
            if match["score"] >= MATCH_THRESHOLD and match["status"] in {"matched", "partial"}
        }
        assigned_asset_ids = {asset["id"] for asset in assets}
        gaps: list[dict[str, Any]] = []
        for segment in structure.script:
            if segment.assetId and segment.assetId in assigned_asset_ids:
                continue
            if segment.id in matched_segment_ids:
                continue
            gaps.append(_gap_for_segment(segment))
        return gaps

    def get_gap(self, project_id: str, gap_id: str) -> dict[str, Any]:
        for gap in self.detect(project_id):
            if gap["id"] == gap_id:
                return gap
        raise GapNotFoundError(f"Gap not found: {gap_id}")


class GapNotFoundError(LookupError):
    pass


def _gap_for_segment(segment: ScriptSegment) -> dict[str, Any]:
    recommended = _recommended_strategy(segment.type)
    return {
        "id": f"gap-{segment.id}",
        "segmentId": segment.id,
        "severity": "critical" if segment.type in {"hook", "cta"} else "warning",
        "description": f"{segment.label} 素材缺口",
        "requiredSlot": f"{segment.start:g}-{segment.end:g}s {segment.label} 画面",
        "selectedStrategyId": recommended,
        "recommendedStrategy": recommended,
        "strategies": STRATEGIES,
        "status": "open",
    }


def _recommended_strategy(segment_type: str) -> str:
    if segment_type == "hook":
        return "reorder"
    if segment_type == "cta":
        return "packaging"
    return "packaging"
