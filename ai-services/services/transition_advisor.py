"""Recommend transitions between segments using LLM when available, static rules as fallback."""

from __future__ import annotations

import json
from typing import Any

import httpx


TRANSITION_PROMPT = """你是短视频转场设计助手。根据相邻两个分镜的内容，推荐最合适的转场效果。

前一个分镜：
- 类型：{from_type}，文案：{from_script}，画面：{from_visual}

后一个分镜：
- 类型：{to_type}，文案：{to_script}，画面：{to_visual}

可选转场：硬切、溶解、缩放、左滑、右滑、闪白、上滑、翻页、模糊切换

返回 JSON：{{"transition":"推荐转场名","reason":"10字以内的中文理由"}}
只返回 JSON，不要解释。"""


class TransitionAdvisor:
    """Recommend transitions based on segment adjacency.

    Uses LLM for content-aware recommendations when available, with static rules as fallback.
    """

    def __init__(
        self,
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        self._llm_available = bool(llm_endpoint and llm_api_key)
        self._endpoint = llm_endpoint
        self._api_key = llm_api_key
        self._model = llm_model

    def recommend(
        self,
        from_type: str,
        to_type: str,
        cuts_at_boundary: int = 3,
        from_script: str = "",
        from_visual: str = "",
        to_script: str = "",
        to_visual: str = "",
        from_source: str = "original",
        to_source: str = "original",
    ) -> list[dict[str, Any]]:
        """Return ordered transition recommendations with reasons."""
        # Try LLM first for content-aware recommendation.
        if self._llm_available:
            llm_result = self._llm_recommend(
                from_type, to_type, from_script, from_visual, to_script, to_visual
            )
            if llm_result:
                # Anti-card safety for LLM path too
                if from_source == "packaging" or to_source == "packaging":
                    llm_result["transition"] = "闪白" if llm_result.get("transition") == "硬切" else llm_result.get("transition", "模糊切换")
                    llm_result["reason"] = "卡片过渡：光效柔化视觉断层"
                return [llm_result]

        # Fallback: static rules (with anti-card safety).
        return _static_recommend(from_type, to_type, cuts_at_boundary, from_source, to_source)

    def recommend_for_script(self, segments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Return transition recommendations for every adjacent pair."""
        recs: dict[str, list[dict[str, Any]]] = {}
        for i in range(len(segments) - 1):
            from_seg = segments[i]
            to_seg = segments[i + 1]
            recs[str(to_seg.get("id", ""))] = self.recommend(
                from_type=str(from_seg.get("type", "")),
                to_type=str(to_seg.get("type", "")),
                from_script=str(from_seg.get("script", "") or from_seg.get("copy", "")),
                from_visual=str(from_seg.get("visual", "")),
                to_script=str(to_seg.get("script", "") or to_seg.get("copy", "")),
                to_visual=str(to_seg.get("visual", "")),
                from_source=str(from_seg.get("source", "original")),
                to_source=str(to_seg.get("source", "original")),
            )
        return recs

    def _llm_recommend(
        self,
        from_type: str, to_type: str,
        from_script: str, from_visual: str,
        to_script: str, to_visual: str,
    ) -> dict[str, Any] | None:
        """Use shared LightLLMClient for content-aware transition recommendation."""
        from services.llm_client import LightLLMClient

        prompt = TRANSITION_PROMPT.format(
            from_type=from_type, from_script=from_script[:80], from_visual=from_visual[:80],
            to_type=to_type, to_script=to_script[:80], to_visual=to_visual[:80],
        )
        try:
            client = LightLLMClient(self._endpoint, self._api_key, self._model)
            content = client.complete_json(prompt, max_tokens=64)
            if isinstance(content, str):
                content = json.loads(content)
            if isinstance(content, dict):
                return {
                    "transition": str(content.get("transition", "硬切")),
                    "score": 85,
                    "reason": str(content.get("reason", "AI推荐"))[:20],
                }
        except Exception:
            pass
        return None


def _static_recommend(
    from_type: str,
    to_type: str,
    cuts_at_boundary: int = 3,
    from_source: str = "original",
    to_source: str = "original",
) -> list[dict[str, Any]]:
    """Static rule-based fallback with anti-card穿帮 safety.

    If either segment is a packaging card (source='packaging'), hard cut is
    FORBIDDEN — the visual gap between real footage and a static card is too
    jarring. Flash or blur transitions mask the seam.
    """
    # ── Anti-card safety: packaging segments get softening transitions ──
    has_card = from_source == "packaging" or to_source == "packaging"
    if has_card:
        return [
            {"transition": "闪白", "score": 95, "reason": "卡片过渡：光效柔化视觉断层"},
            {"transition": "模糊切换", "score": 88, "reason": "卡片过渡：动态模糊抹平PPT感"},
            {"transition": "溶解", "score": 75, "reason": "卡片过渡：慢溶解减轻廉价感"},
        ]

    rules: dict[tuple[str, str], list[tuple[str, str]]] = {
        ("hook", "pain"): [("硬切", "保持冲击力"), ("闪白", "强化情绪转折")],
        ("pain", "product"): [("缩放", "制造解决方案仪式感"), ("硬切", "简洁直接")],
        ("product", "proof"): [("硬切", "保持信息密度"), ("左滑", "模拟阅读节奏")],
        ("proof", "cta"): [("缩放", "聚焦转化"), ("硬切", "强力切入")],
    }
    defaults = [("硬切", "通用默认"), ("溶解", "柔和过渡")]
    candidates = rules.get((from_type, to_type), defaults)
    results: list[dict[str, Any]] = []
    for name, reason in candidates:
        score = 80
        if name == "硬切" and cuts_at_boundary >= 4:
            score = 92
        elif name == "溶解" and cuts_at_boundary <= 2:
            score = 85
        results.append({"transition": name, "score": score, "reason": reason})
    return sorted(results, key=lambda r: -r["score"])


def _extract_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        return payload["choices"][0].get("message", {}).get("content", "")
    if "content" in payload:
        return payload["content"]
    return payload
