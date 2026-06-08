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
    """After 3 invalid LLM attempts, system now falls back to local structure instead of crashing."""
    client = SequenceClient([{"script_structure": []}, {"script_structure": []}, {"bad": True}])

    structure = extract_structure_with_retries(
        client=client,
        prompt_context={"meta": {"duration": 35}},
        max_attempts=3,
    )

    assert client.calls == 3
    # Fallback should produce a valid structure with patched fields
    assert structure.health.overall == 50  # fallback health score
    assert structure.meta.productName == "未知商品"


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
