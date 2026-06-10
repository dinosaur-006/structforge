from __future__ import annotations

from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import ScriptSegment
from services.asset_matcher import AssetMatcher
from services.structure_editor import StructureEditor, StructureNotFoundError


MATCH_THRESHOLD = 60.0

# ── Semantic keyword expansion groups ──
# When visual_requirements mentions a keyword in the group,
# any asset tagged with ANY variant in the same group counts as a match.
SEMANTIC_GROUPS: dict[str, set[str]] = {
    "厨房": {"厨房场景", "灶台", "油烟", "锅具", "料理台", "烹饪"},
    "油污": {"油污", "脏污", "污垢", "重度污渍", "陈年污垢"},
    "卧室": {"卧室梳妆台", "卧室场景", "床品", "梳妆台"},
    "皱眉": {"皱眉抓狂", "不满表情"},
    "手持": {"举起商品", "手持展示", "指向屏幕"},
    "清洁": {"涂抹演示", "泡沫细腻", "液体流动"},
    "对比": {"颜色对比", "内部拆解", "Before/After"},
    "自然光": {"户外自然光"},
    "食物": {"食物特写", "彩色糖果", "颗粒状产品", "独立小包装", "咀嚼展示", "拉丝效果", "酥脆质感"},
    "美妆": {"膏体拉丝", "面部特写", "涂抹演示"},
    "数码": {"材质反光", "内部拆解"},
}

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
        # AIGC is available with either Jimeng or ComfyUI RunningHub
        has_aigc_config = bool(
            (self.settings.jimeng_image_endpoint and self.settings.jimeng_image_api_key)
            or getattr(self.settings, 'runninghub_api_key', None)
            or getattr(self.settings, 'doubao_image_api_key', None)
        )
        aigc_detail = None
        if not has_aigc_config:
            aigc_detail = "未配置图片生成 API，将使用占位风格补全"
        elif getattr(self.settings, 'runninghub_api_key', None):
            aigc_detail = "ComfyUI Flux 文生图可用"
        elif self.settings.jimeng_image_endpoint and self.settings.jimeng_image_api_key:
            aigc_detail = "即梦 AI 图片生成可用"
        else:
            aigc_detail = "豆包 Seedream 图片生成可用"

        # reorder is available when there are matched assets that could fill critical positions.
        has_matched_assets = any(
            asset.get("match_status") in ("matched", "partial") for asset in assets
        )
        availability = {
            "reorder": (has_matched_assets, None if has_matched_assets else "无可匹配的素材用于重排优化"),
            "packaging": (True, None),
            "aigc": (True, aigc_detail),
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


def _semantic_match_score(requirements: dict[str, str], asset_tags: list[str]) -> float:
    """Compute a semantic match score between visual_requirements and asset tags.

    Uses keyword expansion groups to handle synonym variants
    (e.g. "厨房" matches "灶台" or "料理台").
    Returns 0.0–1.0 where 1.0 = perfect match on all dimensions.
    """
    if not requirements or not asset_tags:
        return 0.0

    tags_lower = {t.lower() for t in asset_tags}
    dimensions = 0
    hits = 0

    for key, req_value in requirements.items():
        if not req_value:
            continue
        dimensions += 1
        req_lower = req_value.lower()

        # Direct match
        if req_lower in tags_lower:
            hits += 1
            continue

        # Semantic group match
        for group_key, variants in SEMANTIC_GROUPS.items():
            if group_key in req_lower or any(v in req_lower for v in variants):
                if any(v.lower() in tags_lower for v in variants):
                    hits += 1
                    break

        # Partial overlap (e.g. "满是油污的厨房" contains "油污" + "厨房")
        for tag in tags_lower:
            if len(tag) >= 2 and tag in req_lower:
                hits += 0.5
                break

    return min(1.0, hits / max(dimensions, 1))


def _gap_for_segment(segment: ScriptSegment, strategies: list[dict[str, Any]]) -> dict[str, Any]:
    recommended = _recommended_strategy(segment.type, strategies)
    # Detailed gap descriptions with creative guidance.
    gap_descriptions = {
        "hook": f"缺少开头吸引镜头：需要在{segment.start:g}-{segment.end:g}s制造视觉冲击，建议用冲突画面、悬念特写或产品反转",
        "pain": f"缺少痛点场景镜头：需要展示用户真实困境，建议用生活化场景+情绪特写",
        "product": f"缺少产品展示镜头：需要产品英雄角度特写，建议用商业摄影风格+功能演示",
        "proof": f"缺少卖点证明镜头：需要数据可视化或对比画面，建议用实测/对比/数据展示",
        "cta": f"缺少转化引导镜头：需要价格优惠+行动引导画面，建议用促销视觉+紧迫感元素",
    }
    return {
        "id": f"gap-{segment.id}",
        "segmentId": segment.id,
        "severity": "critical" if segment.type in {"hook", "cta"} else "warning",
        "description": gap_descriptions.get(segment.type, f"{segment.label} 素材缺口"),
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
