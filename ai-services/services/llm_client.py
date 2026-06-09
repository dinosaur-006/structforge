"""Shared robust LLM HTTP client.

Every LLM call in StructForge MUST use this client. LLM is not an optional
feature — it is the engine that drives analysis, migration, auditing, editing,
and all other intelligence layers. Without reliable LLM, the product is dead.

This module provides:
- ``RobustLLMClient``: full 90s timeout + 3-retry (for structure extraction, migration, audit)
- ``LightLLMClient``: 30s timeout + 3-retry (for lightweight calls like classification, transition advice)
- ``llm_post_json``: convenience function that returns parsed JSON directly

Usage::

    from services.llm_client import RobustLLMClient
    client = RobustLLMClient(endpoint, api_key, model)
    result = client.complete_json(prompt)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 90   # seconds — Doubao Seed needs this for complex prompts
LIGHT_TIMEOUT = 30     # seconds — lightweight classification / single-word responses
MAX_RETRIES = 3


class LLMError(RuntimeError):
    """Raised when all LLM retries are exhausted.

    This is NOT a transient warning — it means the core AI engine is unreachable.
    The product MUST surface this to the user, not silently degrade.
    """

    def __init__(
        self,
        message: str,
        *,
        suggestion: str = "",
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.suggestion = suggestion or "请检查 API 配置和网络连接，或稍后重试"
        self.retryable = retryable
        self.status_code = status_code

    def to_dict(self) -> dict[str, object]:
        return {
            "error": "llm_unavailable",
            "message": str(self),
            "suggestion": self.suggestion,
            "retryable": self.retryable,
            "status_code": self.status_code,
        }


class RobustLLMClient:
    """Full-featured LLM client with 90s timeout + 3 retries.

    Use for: structure extraction, script migration, burst audit, qualitative review.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = "doubao-seed-2-0-lite",
        *,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        if not endpoint or not api_key:
            raise LLMError("LLM endpoint and API key are required")
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def available(self) -> bool:
        return bool(self._endpoint and self._api_key)

    def complete_json(
        self, prompt: str, *, max_tokens: int = 2048,
        response_type: type | None = None,
    ) -> object:
        """Send prompt, return parsed JSON or Pydantic model.

        When response_type is provided (a Pydantic BaseModel subclass),
        the JSON Schema is injected into the prompt to guide the LLM.
        Returns a validated model instance on success.
        """
        enhanced = prompt
        if response_type is not None:
            schema_instruction = _build_schema_instruction(response_type)
            enhanced = f"{prompt}\n\n{schema_instruction}"
        raw = self._call(enhanced, max_tokens=max_tokens)
        parsed = _parse_content(raw)
        if response_type is not None and isinstance(parsed, dict):
            return response_type.model_validate(parsed)
        return parsed

    def complete_text(self, prompt: str, *, max_tokens: int = 256) -> str:
        """Send prompt, return raw text. Raises LLMError on failure."""
        return self._call(prompt, max_tokens=max_tokens)

    def _call(self, prompt: str, *, max_tokens: int = 2048) -> str:
        last_error: str | None = None
        last_status: int | None = None
        for attempt in range(self._max_retries):
            try:
                resp = httpx.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    },
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                content = _extract_content(payload)
                if isinstance(content, str):
                    return content
                return str(content)
            except httpx.ReadTimeout:
                last_error = "LLM 调用超时"
                last_status = None
                if attempt < self._max_retries - 1:
                    delay = 0.5 * (attempt + 1)
                    log.warning("LLM timeout attempt %d/%d, retrying in %.1fs",
                                attempt + 1, self._max_retries, delay)
                    time.sleep(delay)
                    continue
            except httpx.HTTPStatusError as exc:
                last_error = str(exc)
                last_status = exc.response.status_code
                if last_status == 401 or last_status == 403:
                    # Auth errors are not retryable — API key is invalid
                    raise LLMError(
                        "API Key 无效或已过期",
                        suggestion="请前往设置页面更新 STRUCTFORGE_DOUBAO_LLM_API_KEY",
                        retryable=False,
                        status_code=last_status,
                    )
                if last_status >= 500 and attempt < self._max_retries - 1:
                    delay = 1.0 * (attempt + 1)
                    log.warning("LLM server error %d attempt %d/%d, retrying in %.1fs",
                                last_status, attempt + 1, self._max_retries, delay)
                    time.sleep(delay)
                    continue
            except (httpx.RemoteProtocolError, httpx.RequestError) as exc:
                last_error = str(exc)
                last_status = None
                if attempt < self._max_retries - 1:
                    delay = 0.5 * (attempt + 1)
                    log.warning("LLM network error attempt %d/%d, retrying in %.1fs: %s",
                                attempt + 1, self._max_retries, delay, last_error)
                    time.sleep(delay)
                    continue

        # All retries exhausted
        if last_status and last_status >= 500:
            raise LLMError(
                f"LLM 服务暂时不可用（HTTP {last_status}），已重试 {self._max_retries} 次",
                suggestion="服务端过载，请稍后重试。如持续出现，可尝试切换模型。",
                retryable=True,
                status_code=last_status,
            )
        if last_error and "超时" in last_error:
            raise LLMError(
                f"LLM 调用超时（{self._timeout}s），已重试 {self._max_retries} 次",
                suggestion="请检查网络连接。如持续超时，可在 .env 中调高 STRUCTFORGE_LLM_TIMEOUT_SECONDS。",
                retryable=True,
                status_code=None,
            )
        raise LLMError(
            f"LLM 请求失败，已重试 {self._max_retries} 次。最后错误: {last_error}",
            suggestion="请检查 API 配置和网络连接，或稍后重试",
            retryable=True,
            status_code=last_status,
        )


class LightLLMClient(RobustLLMClient):
    """Lightweight LLM client with 30s timeout + 3 retries.

    Use for: scene classification, transition advice, subtitle detection,
    content safety review, highlight detection, asset matching.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = "doubao-seed-2-0-lite",
    ) -> None:
        super().__init__(endpoint, api_key, model, timeout=LIGHT_TIMEOUT, max_retries=MAX_RETRIES)


def llm_post_json(
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    *,
    max_tokens: int = 256,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Convenience: one-shot LLM call returning parsed JSON dict.

    Uses the same retry logic as RobustLLMClient internally.
    Suitable for simple endpoints that don't need a persistent client instance.
    """
    client = RobustLLMClient(endpoint, api_key, model, timeout=timeout)
    result = client.complete_json(prompt, max_tokens=max_tokens)
    if isinstance(result, dict):
        return result
    try:
        return json.loads(str(result))
    except json.JSONDecodeError:
        return {"raw_response": str(result)}


# ── Internal helpers (shared with llm_structure.py) ──

def _extract_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        message = payload["choices"][0].get("message", {})
        return message.get("content", "")
    if "content" in payload:
        return payload["content"]
    return payload


def _parse_content(content: str) -> object:
    """Parse JSON from LLM response, with markdown fence stripping."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Strip ```json fences if present
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            if len(lines) >= 2 and lines[0].startswith("```"):
                lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # remove closing fence
            stripped = "\n".join(lines).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            # Last resort: find first JSON object
            candidate = _first_json_object(stripped)
            if candidate:
                return json.loads(candidate)
            raise


def _build_schema_instruction(response_type: type) -> str:
    """Build JSON Schema injection for LLM prompt.

    Appends a simplified JSON Schema to the prompt so the LLM knows
    exactly what format to output. Ported from Pixelle-Video's
    LLMService._get_json_schema_instruction().

    Only top-level keys and required fields are included — full nested
    schemas are too long and the LLM tends to ignore them.
    """
    import json as _json
    try:
        schema = response_type.model_json_schema()
    except Exception:
        return "Respond with ONLY a valid JSON object. No markdown, no extra text."

    # Simplify: keep only top-level structure
    simplified: dict = {"type": "object"}
    if "properties" in schema:
        keys = list(schema["properties"].keys())[:20]
        required = [k for k in (schema.get("required") or []) if k in keys]
        simplified["required"] = required
        simplified["properties"] = {k: _simplify_prop(schema["properties"][k]) for k in keys}
    if "title" in schema:
        simplified["title"] = schema["title"]

    schema_str = _json.dumps(simplified, indent=2, ensure_ascii=False)
    return (
        "## OUTPUT FORMAT (MANDATORY — VIOLATION WILL CAUSE REJECTION)\n"
        "You MUST respond with ONLY a valid JSON object matching this exact schema.\n"
        "No markdown fences, no explanation, no extra text — PURE JSON ONLY.\n\n"
        f"Schema:\n```json\n{schema_str}\n```\n\n"
        "YOUR RESPONSE (JSON only):"
    )


def _simplify_prop(prop: dict) -> dict:
    """Keep only type + description from a property schema."""
    simple: dict = {}
    if "type" in prop:
        simple["type"] = prop["type"]
    if "description" in prop and len(str(prop["description"])) < 80:
        simple["description"] = str(prop["description"])[:80]
    if "items" in prop and isinstance(prop["items"], dict):
        simple["items"] = _simplify_prop(prop["items"])
    return simple


def _first_json_object(content: str) -> str | None:
    start = content.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(content)):
            char = content[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start : index + 1]
        start = content.find("{", start + 1)
    return None
