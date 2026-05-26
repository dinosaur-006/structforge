from __future__ import annotations

from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import ScriptSegment
from services.asset_matcher import AssetMatcher
from services.structure_editor import StructureEditor, StructureNotFoundError


MATCH_THRESHOLD = 60.0

STRATEGY_DEFINITIONS = [
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
        "description": "使用生成式图片补足缺失画面；仅在配置即梦服务后可用。",
    },
    {
        "id": "recompose",
        "name": "素材重组",
        "description": "复用现有视频素材进行裁切或重组；需要已上传的视频素材。",
    },
]


class GapDetector:
    def __init__(self, repository: SQLiteRepository, settings: Settings | None = None) -> None:
        self.repository = repository
        self.settings = settings or Settings()
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
            gaps.append(_gap_for_segment(segment, self._available_strategies(assets)))
        return gaps

    def get_gap(self, project_id: str, gap_id: str) -> dict[str, Any]:
        for gap in self.detect(project_id):
            if gap["id"] == gap_id:
                return gap
        raise GapNotFoundError(f"Gap not found: {gap_id}")

    def _available_strategies(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        has_video_asset = any(asset["type"] == "video" and asset.get("file_path") for asset in assets)
        has_aigc_config = bool(self.settings.jimeng_image_endpoint and self.settings.jimeng_image_api_key)
        availability = {
            "reorder": (False, "结构重排保留为人工编辑操作"),
            "packaging": (True, None),
            "aigc": (has_aigc_config, None if has_aigc_config else "未配置即梦 API"),
            "recompose": (has_video_asset, None if has_video_asset else "需要可用视频素材"),
        }
        return [
            {
                **definition,
                "available": availability[definition["id"]][0],
                "unavailableReason": availability[definition["id"]][1],
            }
            for definition in STRATEGY_DEFINITIONS
        ]


class GapNotFoundError(LookupError):
    pass


def _gap_for_segment(segment: ScriptSegment, strategies: list[dict[str, Any]]) -> dict[str, Any]:
    recommended = _recommended_strategy(segment.type, strategies)
    return {
        "id": f"gap-{segment.id}",
        "segmentId": segment.id,
        "severity": "critical" if segment.type in {"hook", "cta"} else "warning",
        "description": f"{segment.label} 素材缺口",
        "requiredSlot": f"{segment.start:g}-{segment.end:g}s {segment.label} 画面",
        "selectedStrategyId": recommended,
        "recommendedStrategy": recommended,
        "strategies": strategies,
        "status": "open",
    }


def _recommended_strategy(segment_type: str, strategies: list[dict[str, Any]]) -> str:
    preferred = "packaging" if segment_type in {"hook", "cta"} else "recompose"
    if any(strategy["id"] == preferred and strategy["available"] for strategy in strategies):
        return preferred
    return "packaging"
