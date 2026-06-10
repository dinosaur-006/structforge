from __future__ import annotations

import json
from typing import Any

import httpx

from models.repository import SQLiteRepository
from services.structure_editor import StructureEditor, StructureNotFoundError


ROLE_KEYWORDS = {
    "hook": ["冲突", "悬念", "特写", "问题", "对比"],
    "pain": ["场景", "困境", "人物", "情绪"],
    "product": ["产品特写", "产品", "功能", "包装"],
    "proof": ["演示", "对比", "数据", "证言"],
    "cta": ["价格", "优惠", "购买", "Logo", "行动"],
}

SEGMENT_ROLE_DESC: dict[str, str] = {
    "hook": "开头吸引：需要冲突画面、悬念特写、问题揭示类素材",
    "pain": "痛点场景：需要困境表达、使用场景、情绪类素材",
    "product": "产品展示：需要产品特写、功能演示、开箱、包装类素材",
    "proof": "卖点证明：需要对比测试、数据展示、实测效果类素材",
    "cta": "转化引导：需要价格优惠、Logo展示、购买引导类素材",
}

MATCH_PROMPT = """你是短视频素材匹配助手。给定素材描述和分镜槽位需求，判断每个素材最适合填充哪个槽位。

槽位需求：
{segment_descriptions}

素材列表：
{asset_descriptions}

返回一个 JSON 对象，格式为：
{{"matches":[{{"asset_id":"...","segment_id":"...","score":0-100,"reason":"简短理由"}}]}}
- 每个素材只需返回最匹配的 1-2 个槽位
- score 表示匹配程度：80+ 非常适合，50-79 部分适合，<50 不适合
- reason 用中文写，10字以内
- 只返回 JSON，不要解释"""


def match_status(score: float) -> str:
    if score >= 80:
        return "matched"
    if score >= 50:
        return "partial"
    return "unmatched"


class AssetMatcher:
    def __init__(
        self,
        repository: SQLiteRepository,
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        self.repository = repository
        self.structure_editor = StructureEditor(repository)
        self._llm_available = bool(llm_endpoint and llm_api_key)
        self._endpoint = llm_endpoint
        self._api_key = llm_api_key
        self._model = llm_model

    def match_project_assets(self, project_id: str) -> list[dict[str, Any]]:
        if self.repository.get_project(project_id) is None:
            raise StructureNotFoundError(f"Project not found: {project_id}")

        structure = self.structure_editor.get_structure(project_id)
        assets = self.repository.list_assets(project_id)

        if not assets:
            return []

        # Rule-based keyword matching (fast, no LLM call needed)
        matches: list[dict[str, Any]] = []
        best_by_asset: dict[str, tuple[float, str]] = {}

        for asset in assets:
            searchable = _asset_searchable_text(asset)
            for segment in structure.script:
                score = _keyword_score(searchable, ROLE_KEYWORDS.get(segment.type, []))

                # ── Scene type boost: direct type match → +25 ──
                asset_scene = str((asset.get("analysis") or {}).get("scene_type", "") or "")
                if asset_scene == segment.type:
                    score = min(score + 25, 100)

                status = match_status(score)
                matches.append({
                    "asset_id": asset["id"],
                    "segment_id": segment.id,
                    "score": score,
                    "status": status,
                })
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
                {"segmentId": match["segment_id"], "label": segment_by_id[match["segment_id"]].label, "score": match["score"]}
                for match in ranked
            ]
            if segments:
                tag = asset.get("tag") or asset["name"]
                recommendations[asset["id"]] = {
                    "recommendedSegments": segments,
                    "reason": f"适合 {segments[0]['label']}：{tag} 与该结构槽位需求匹配",
                }
            else:
                recommendations[asset["id"]] = {
                    "recommendedSegments": [],
                    "reason": "暂无高可信推荐，建议补充更清晰的素材内容",
                }
        return recommendations

    def _llm_match(self, assets: list[dict[str, Any]], segments: Any) -> dict[tuple[str, str], float]:
        """Use Doubao LLM for semantic asset-to-segment matching."""
        segment_descs = "\n".join(
            f"- {s.id} ({s.type}): {SEGMENT_ROLE_DESC.get(s.type, s.label)} 目标: {s.goal}"
            for s in segments
        )
        asset_descs = "\n".join(
            f"- {a['id']}: 名称={a.get('name','')} 标签={a.get('tag','')} "
            f"描述={(a.get('analysis') or {}).get('description','')} "
            f"OCR={(a.get('analysis') or {}).get('ocr_text','')}"
            for a in assets
        )
        prompt = MATCH_PROMPT.format(
            segment_descriptions=segment_descs,
            asset_descriptions=asset_descs,
        )
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            content = _extract_llm_content(payload)
            if isinstance(content, str):
                content = json.loads(content)
            results: dict[tuple[str, str], float] = {}
            for m in content.get("matches", []) if isinstance(content, dict) else []:
                aid = str(m.get("asset_id", ""))
                sid = str(m.get("segment_id", ""))
                score = float(m.get("score", 0))
                if aid and sid:
                    results[(aid, sid)] = min(max(score, 0), 100)
            return results
        except Exception:
            return {}


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


def _keyword_score(searchable: str, keywords: list[str]) -> float:
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


def _extract_llm_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        return payload["choices"][0].get("message", {}).get("content", "")
    if "content" in payload:
        return payload["content"]
    return payload
