"""Classify uploaded assets into the 5 segment types using LLM semantic understanding.

Falls back to keyword matching when LLM is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


SEGMENT_DEFINITIONS: dict[str, str] = {
    "hook": "开头吸引画面：冲突、悬念、特写、问题揭示、抓眼球的内容",
    "pain": "痛点场景：用户困境、情绪表达、使用场景、烦恼时刻",
    "product": "产品展示：开箱、功能演示、包装特写、产品亮相",
    "proof": "卖点证明：对比测试、数据展示、证言、实测效果、before/after",
    "cta": "转化引导：价格优惠、购买链接、Logo展示、限时活动、行动号召",
}

CLASSIFY_PROMPT = """你是短视频素材概率分类助手。根据素材描述，计算它对 5 种结构槽位的适配概率矩阵。

不要再玩非黑即白的单选游戏——那会导致大面积素材被误杀而被迫降级为卡片！

## 5 种槽位定义
{hook}
{pain}
{product}
{proof}
{cta}

## 素材描述
- 标签：{tags}
- 画面描述：{description}
- OCR文字：{ocr}

## 输出格式
返回严格 JSON 对象，包含 5 个类目的概率（0.0-1.0），必须有 justification 字段：
{{"asset_id":"...","predictions":{{"hook":0.85,"pain":0.50,"product":0.30,"proof":0.10,"cta":0.05}},"best_type":"hook","justification":"10字内中文理由"}}

只返回 JSON，不要解释。"""


class SceneClassifier:
    """Classify assets into structure segment types. Uses LLM when available, keyword fallback otherwise."""

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

    def classify(self, analysis: dict[str, Any]) -> str | None:
        """Return the best-matching segment type or None."""
        tags = [str(t).strip() for t in (analysis.get("tags") or [])]
        description = str(analysis.get("description") or "")
        ocr = str(analysis.get("ocr_text") or "")

        # Try LLM first.
        if self._llm_available:
            result = self._llm_classify(tags, description, ocr)
            if result:
                return result

        # Fallback: keyword matching.
        return _keyword_classify(tags, description, ocr)

    def classify_file(self, path: Path, existing_analysis: dict[str, Any] | None = None) -> str | None:
        """Classify a file by analysis data, falling back to filename."""
        if existing_analysis:
            result = self.classify(existing_analysis)
            if result:
                return result

        return _keyword_classify_file(path)

    def _llm_classify(self, tags: list[str], description: str, ocr: str) -> str | None:
        """Use Doubao LLM to semantically classify the asset with probability matrix."""
        prompt = CLASSIFY_PROMPT.format(
            hook=SEGMENT_DEFINITIONS["hook"],
            pain=SEGMENT_DEFINITIONS["pain"],
            product=SEGMENT_DEFINITIONS["product"],
            proof=SEGMENT_DEFINITIONS["proof"],
            cta=SEGMENT_DEFINITIONS["cta"],
            tags=", ".join(tags) if tags else "无",
            description=description or "无",
            ocr=ocr or "无",
        )
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 128,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            content = _extract_content(payload)
            if isinstance(content, str):
                content = json.loads(content)
            # New format: probability matrix
            if isinstance(content, dict) and "best_type" in content:
                result_type = str(content["best_type"]).strip().lower()
                if result_type in SEGMENT_DEFINITIONS:
                    return result_type
            # Old format: single type field
            result_type = str(content.get("type", "")).strip().lower()
            if result_type in SEGMENT_DEFINITIONS:
                return result_type
        except Exception:
            pass
        return None


def _keyword_classify(tags: list[str], description: str, ocr: str) -> str | None:
    """Keyword-based fallback classification."""
    keywords = {
        "hook": ["冲突", "悬念", "特写", "问题", "对比", "conflict", "hook", "抓眼球"],
        "pain": ["场景", "困境", "人物", "情绪", "scene", "pain", "通勤", "烦恼"],
        "product": ["产品", "功能", "包装", "开箱", "product", "demo", "展示"],
        "proof": ["演示", "对比", "数据", "证言", "proof", "data", "review", "测试"],
        "cta": ["价格", "优惠", "购买", "Logo", "cta", "buy", "行动", "限时"],
    }
    searchable = f"{' '.join(tags).lower()} {description.lower()} {ocr.lower()}"
    scores: dict[str, int] = {}
    for seg_type, kws in keywords.items():
        hits = sum(1 for kw in kws if kw.lower() in searchable)
        if hits:
            scores[seg_type] = hits
    return max(scores, key=lambda k: scores[k]) if scores else None


def _keyword_classify_file(path: Path) -> str | None:
    """Filename-based fallback classification."""
    keywords = {
        "hook": ["冲突", "悬念", "特写", "问题", "对比", "conflict", "hook", "抓眼球"],
        "pain": ["场景", "困境", "人物", "情绪", "scene", "pain", "通勤", "烦恼"],
        "product": ["产品", "功能", "包装", "开箱", "product", "demo", "展示"],
        "proof": ["演示", "对比", "数据", "证言", "proof", "data", "review", "测试"],
        "cta": ["价格", "优惠", "购买", "Logo", "cta", "buy", "行动", "限时"],
    }
    name = path.name.lower()
    for seg_type, kws in keywords.items():
        if any(kw.lower() in name for kw in kws):
            return seg_type
    return None


def _extract_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        return payload["choices"][0].get("message", {}).get("content", "")
    if "content" in payload:
        return payload["content"]
    return payload
