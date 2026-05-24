from __future__ import annotations

import pytest

from services.llm_structure import StructureExtractionError, _parse_json_content, extract_structure_with_retries
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
    client = SequenceClient([{"script_structure": []}, {"script_structure": []}, {"bad": True}])

    with pytest.raises(StructureExtractionError):
        extract_structure_with_retries(
            client=client,
            prompt_context={"meta": {"duration": 35}},
            max_attempts=3,
        )

    assert client.calls == 3


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
