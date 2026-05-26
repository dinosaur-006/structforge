from __future__ import annotations

from typing import Any

from models.repository import SQLiteRepository
from services.structure_editor import StructureEditor, StructureNotFoundError


ROLE_KEYWORDS = {
    "hook": ["冲突", "悬念", "特写", "问题", "对比"],
    "pain": ["场景", "困境", "人物", "情绪"],
    "product": ["产品特写", "产品", "功能", "包装"],
    "proof": ["演示", "对比", "数据", "证言"],
    "cta": ["价格", "优惠", "购买", "Logo", "行动"],
}


def match_status(score: float) -> str:
    if score >= 80:
        return "matched"
    if score >= 50:
        return "partial"
    return "unmatched"


class AssetMatcher:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.structure_editor = StructureEditor(repository)

    def match_project_assets(self, project_id: str) -> list[dict[str, Any]]:
        if self.repository.get_project(project_id) is None:
            raise StructureNotFoundError(f"Project not found: {project_id}")

        structure = self.structure_editor.get_structure(project_id)
        assets = self.repository.list_assets(project_id)
        matches: list[dict[str, Any]] = []
        best_by_asset: dict[str, tuple[float, str]] = {}

        for asset in assets:
            searchable = _asset_searchable_text(asset)
            for segment in structure.script:
                score = _score(searchable, ROLE_KEYWORDS.get(segment.type, []))
                status = match_status(score)
                matches.append(
                    {
                        "asset_id": asset["id"],
                        "segment_id": segment.id,
                        "score": score,
                        "status": status,
                    }
                )
                current_best = best_by_asset.get(asset["id"], (0.0, "unmatched"))
                if score > current_best[0]:
                    best_by_asset[asset["id"]] = (score, status)

        for asset in assets:
            score, status = best_by_asset.get(asset["id"], (0.0, "unmatched"))
            self.repository.update_asset_match(asset["id"], score=score, status=status)

        return matches

    def recommend_project_assets(self, project_id: str) -> dict[str, dict[str, Any]]:
        structure = self.structure_editor.get_structure(project_id)
        matches = self.match_project_assets(project_id)
        segment_by_id = {segment.id: segment for segment in structure.script}
        recommendations: dict[str, dict[str, Any]] = {}
        for asset in self.repository.list_assets(project_id):
            ranked = sorted(
                (match for match in matches if match["asset_id"] == asset["id"] and match["score"] >= 50),
                key=lambda match: match["score"],
                reverse=True,
            )[:2]
            segments = [
                {
                    "segmentId": match["segment_id"],
                    "label": segment_by_id[match["segment_id"]].label,
                    "score": match["score"],
                }
                for match in ranked
            ]
            if segments:
                recommendations[asset["id"]] = {
                    "recommendedSegments": segments,
                    "reason": f"适合 {segments[0]['label']}：{asset.get('tag') or asset['name']} 与该结构槽位需求匹配",
                }
            else:
                recommendations[asset["id"]] = {
                    "recommendedSegments": [],
                    "reason": "暂无高可信推荐，建议补充更清晰的素材内容",
                }
        return recommendations


def _asset_searchable_text(asset: dict[str, Any]) -> str:
    analysis = asset.get("analysis") or {}
    if not analysis:
        return ""
    parts: list[str] = [
        str(asset.get("name") or ""),
        str(asset.get("tag") or ""),
        str(analysis.get("description") or ""),
        str(analysis.get("ocr_text") or ""),
    ]
    tags = analysis.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(tag) for tag in tags)
    return " ".join(part for part in parts if part).lower()


def _score(searchable: str, keywords: list[str]) -> float:
    if not searchable:
        return 0.0
    hits = sum(1 for keyword in keywords if keyword.lower() in searchable)
    if hits >= 2:
        return 92.0
    if hits == 1:
        return 84.0
    weak_keywords = ["素材", "图片", "视频", "文案", "demo", "product", "offer", "conflict"]
    if any(keyword in searchable for keyword in weak_keywords):
        return 45.0
    return 0.0
