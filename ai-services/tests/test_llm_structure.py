from __future__ import annotations

import pytest

from services.llm_structure import StructureExtractionError, extract_structure_with_retries
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
