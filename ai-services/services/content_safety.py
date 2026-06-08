"""Content safety review for generated scripts and analysis results.

Implements a multi-layer approach:
1. Keyword blocklist (fast, always-on)
2. LLM-based content review (semantic understanding, when LLM is available)
"""

from __future__ import annotations

import re
from typing import Any

import httpx


# Default blocked terms – customize via config.
DEFAULT_BLOCKED_TERMS: list[str] = [
    "赌博", "赌场", "彩票", "色情", "裸体",
    "暴力", "杀人", "毒品", "吸毒", "贩毒",
    "仇恨言论", "种族歧视",
]

LLM_REVIEW_PROMPT = """你是 StructForge 的安全合规与重写助手。审查以下短视频脚本文案是否包含极限词或违规项。

违规项: 赌博、色情、暴力、毒品、仇恨言论、欺诈、虚假宣传、极限词（"全网第一""最强""永久""100%"等绝对化用语）、未经证实的产品功效声称。

## 重要：严禁直接返回 YES 阻断生成链路！
你必须返回合规检查状态。若违规，必须在 safe_rewrite 中给出替换敏感词后的安全文案，确保下游渲染流能平稳拿到文本。

脚本内容：
{content}

## 输出 JSON 格式：
{{"is_violating": true|false, "violation_reason": "违规原因（如无违规则填空）", "original_copy": "原始违规片段", "safe_rewrite": "替换敏感词后的安全文案"}}
只返回 JSON，不要解释。"""


class ContentSafetyResult:
    def __init__(self, passed: bool, warnings: list[str], blocked: list[str]) -> None:
        self.passed = passed
        self.warnings = warnings
        self.blocked = blocked


class ContentSafetyService:
    def __init__(
        self,
        blocked_terms: str = "",
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        custom = [t.strip() for t in (blocked_terms or "").split(",") if t.strip()]
        self.blocked_terms = custom if custom else DEFAULT_BLOCKED_TERMS
        self._llm_available = bool(llm_endpoint and llm_api_key)
        self._endpoint = llm_endpoint
        self._api_key = llm_api_key
        self._model = llm_model

    def check_text(self, text: str) -> ContentSafetyResult:
        """Check a single text string for prohibited content.

        If violations are found, tries LLM to generate a safe rewrite.
        Does NOT block the pipeline — returns rewrite suggestion instead.
        """
        warnings: list[str] = []
        blocked: list[str] = []
        lower = text.lower()

        for term in self.blocked_terms:
            if term.lower() in lower:
                blocked.append(f"检测到禁止词: {term}")

        # Simple pattern checks.
        if re.search(r"(?:微信|联系方式|加好友).{0,10}(?:\d{6,})", text):
            warnings.append("检测到疑似联系方式")

        # Try LLM rewrite for blocked content.
        if blocked and self._llm_available and self._endpoint and self._api_key:
            try:
                import json, httpx
                response = httpx.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": LLM_REVIEW_PROMPT.format(content=text[:3000])}],
                        "max_tokens": 256,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                content = ""
                if "choices" in payload:
                    content = payload["choices"][0].get("message", {}).get("content", "")
                if content.strip().startswith("{"):
                    result = json.loads(content.strip())
                    if result.get("safe_rewrite"):
                        warnings.append(f"已生成安全替代文案，原违规内容: {result.get('violation_reason', '未知')}")
            except Exception:
                pass  # LLM unavailable — fall through to keyword-only check

        passed = len(blocked) == 0
        return ContentSafetyResult(passed=passed, warnings=warnings, blocked=blocked)

    def check_script(self, script: dict[str, Any]) -> ContentSafetyResult:
        """Check all text content in a FinalScript."""
        all_warnings: list[str] = []
        all_blocked: list[str] = []
        all_text: list[str] = []

        segments = script.get("segments", [])
        for seg in segments:
            for field in ("script", "visual", "subtitle_style"):
                value = str(seg.get(field, ""))
                result = self.check_text(value)
                all_warnings.extend(result.warnings)
                all_blocked.extend(result.blocked)
                if value.strip():
                    all_text.append(value)

        metadata = script.get("metadata", {})
        for field in ("edit_reason", "edit_plan"):
            value = str(metadata.get(field, ""))
            result = self.check_text(value)
            all_warnings.extend(result.warnings)
            all_blocked.extend(result.blocked)

        # LLM semantic review (supplementary to keyword check).
        if self._llm_available and all_text:
            llm_warning = self._llm_review("\n".join(all_text))
            if llm_warning:
                all_warnings.append(llm_warning)

        passed = len(all_blocked) == 0
        return ContentSafetyResult(
            passed=passed,
            warnings=list(set(all_warnings)),
            blocked=list(set(all_blocked)),
        )

    def check_structure(self, structure: dict[str, Any]) -> ContentSafetyResult:
        """Check text content in a VideoStructure."""
        all_warnings: list[str] = []
        all_blocked: list[str] = []
        all_text: list[str] = []

        segments = structure.get("script", [])
        for seg in segments:
            for field in ("copy", "visual", "label"):
                value = str(seg.get(field, ""))
                result = self.check_text(value)
                all_warnings.extend(result.warnings)
                all_blocked.extend(result.blocked)
                if value.strip():
                    all_text.append(value)

        if self._llm_available and all_text:
            llm_warning = self._llm_review("\n".join(all_text))
            if llm_warning:
                all_warnings.append(llm_warning)

        passed = len(all_blocked) == 0
        return ContentSafetyResult(
            passed=passed,
            warnings=list(set(all_warnings)),
            blocked=list(set(all_blocked)),
        )

    def _llm_review(self, content: str) -> str | None:
        """Use LLM for semantic content review. Returns warning string or None."""
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": LLM_REVIEW_PROMPT.format(content=content[:3000])}],
                    "max_tokens": 8,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            text = ""
            if "choices" in payload:
                text = payload["choices"][0].get("message", {}).get("content", "")
            answer = str(text).strip().upper()
            if answer.startswith("YES"):
                return "LLM 审核标记：内容可能包含违规信息，建议人工复核"
        except Exception:
            pass
        return None
