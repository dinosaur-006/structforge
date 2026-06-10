from __future__ import annotations

import json

import httpx
import pytest

from config import Settings
from services.llm_structure import (
    DoubaoSeedClient,
    StructureExtractionError,
    _parse_json_content,
    extract_structure_with_retries,
)
from tests.test_schemas import valid_video_structure_payload


class SequenceClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls = 0

    def complete_json(self, prompt: str) -> object:
        self.calls += 1
        return self.responses[self.calls - 1]


def test_llm_extraction_retries_invalid_payloads_until_valid() -> None:
    client = SequenceClient(
        [
            {"script_structure": []},
            {"meta": {}},
            valid_video_structure_payload(),
        ]
    )

    structure = extract_structure_with_retries(
        client=client,
        prompt_context={"meta": {"duration": 35}},
        max_attempts=3,
    )

    assert client.calls == 3
    assert structure.health.overall == 72


def test_llm_extraction_fails_after_three_invalid_attempts() -> None:
    """After 3 invalid LLM attempts, system raises LLMError — no silent degradation."""
    import pytest
    from services.llm_client import LLMError

    client = SequenceClient([{"script_structure": []}, {"script_structure": []}, {"bad": True}])

    with pytest.raises(LLMError) as exc_info:
        extract_structure_with_retries(
            client=client,
            prompt_context={"meta": {"duration": 35}},
            max_attempts=3,
        )

    assert client.calls == 3
    assert "3 次全部失败" in str(exc_info.value)
    assert exc_info.value.retryable is True
    assert exc_info.value.suggestion != ""


def test_parse_json_content_extracts_object_from_markdown_response() -> None:
    payload = _parse_json_content(
        'Here is the result:\n```json\n{"ok": true, "nested": {"value": "brace } inside string"}}\n```'
    )

    assert payload == {"ok": True, "nested": {"value": "brace } inside string"}}


def test_llm_extraction_normalizes_short_rhythm_series() -> None:
    payload = valid_video_structure_payload()
    payload["rhythm"] = payload["rhythm"][:3]
    client = SequenceClient([payload])

    structure = extract_structure_with_retries(
        client=client,
        prompt_context={"meta": {"duration": 35}},
        max_attempts=1,
    )

    assert len(structure.rhythm) >= 5


def test_doubao_transport_disconnect_is_retried(monkeypatch) -> None:
    calls = 0
    request = httpx.Request("POST", "https://unit.test/chat")

    def fake_post(*args, **kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.", request=request)
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json.dumps(valid_video_structure_payload())}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = DoubaoSeedClient(
        Settings(doubao_llm_endpoint="https://unit.test/chat", doubao_llm_api_key="test")
    )

    structure = extract_structure_with_retries(
        client=client,
        prompt_context={"meta": {"duration": 35}},
        max_attempts=2,
    )

    assert calls == 2
    assert structure.health.overall == 72


def test_llm_error_to_dict_serialization():
    """LLMError.to_dict() produces frontend-consumable JSON structure."""
    from services.llm_client import LLMError

    e = LLMError("test message", suggestion="请检查 API Key", retryable=False, status_code=401)
    d = e.to_dict()

    assert d["error"] == "llm_unavailable"
    assert d["message"] == "test message"
    assert d["suggestion"] == "请检查 API Key"
    assert d["retryable"] is False
    assert d["status_code"] == 401


def test_llm_client_retries_transient_network_error(monkeypatch):
    """Transient network errors should be retried, not immediately raised."""
    from services.llm_client import RobustLLMClient
    import httpx as _httpx

    calls = 0
    request = _httpx.Request("POST", "https://unit.test/chat")

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise _httpx.RemoteProtocolError("Server disconnected", request=request)
        return _httpx.Response(200, request=request, json={
            "choices": [{"message": {"content": '{"status":"ok"}'}}]
        })

    monkeypatch.setattr(_httpx, "post", fake_post)
    client = RobustLLMClient("https://unit.test/chat", "test-key", "test-model", max_retries=3)
    result = client.complete_json("test")
    assert calls == 3
    assert result == {"status": "ok"}


def test_doubao_http_service_error_is_retried(monkeypatch) -> None:
    calls = 0
    request = httpx.Request("POST", "https://unit.test/chat")

    def fake_post(*args, **kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request, json={"error": {"message": "temporarily unavailable"}})
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json.dumps(valid_video_structure_payload())}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = DoubaoSeedClient(
        Settings(doubao_llm_endpoint="https://unit.test/chat", doubao_llm_api_key="test")
    )

    structure = extract_structure_with_retries(
        client=client,
        prompt_context={"meta": {"duration": 35}},
        max_attempts=2,
    )

    assert calls == 2
    assert structure.health.overall == 72


def test_llm_error_to_dict_serialization():
    """LLMError.to_dict() produces frontend-consumable JSON structure."""
    from services.llm_client import LLMError

    e = LLMError("test message", suggestion="请检查 API Key", retryable=False, status_code=401)
    d = e.to_dict()

    assert d["error"] == "llm_unavailable"
    assert d["message"] == "test message"
    assert d["suggestion"] == "请检查 API Key"
    assert d["retryable"] is False
    assert d["status_code"] == 401


def test_llm_client_retries_transient_network_error(monkeypatch):
    """Transient network errors should be retried, not immediately raised."""
    from services.llm_client import RobustLLMClient
    import httpx as _httpx

    calls = 0
    request = _httpx.Request("POST", "https://unit.test/chat")

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise _httpx.RemoteProtocolError("Server disconnected", request=request)
        return _httpx.Response(200, request=request, json={
            "choices": [{"message": {"content": '{"status":"ok"}'}}]
        })

    monkeypatch.setattr(_httpx, "post", fake_post)
    client = RobustLLMClient("https://unit.test/chat", "test-key", "test-model", max_retries=3)
    result = client.complete_json("test")
    assert calls == 3
    assert result == {"status": "ok"}
