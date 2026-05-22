from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.schemas import TaskProgress, VideoStructure


def valid_video_structure_payload() -> dict:
    return {
        "meta": {
            "duration": 35.0,
            "resolution": "1080x1920",
            "shots": 12,
            "coverLabel": "Frame 1",
        },
        "script": [
            {
                "id": "seg-1",
                "type": "hook",
                "label": "Hook",
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "goal": "stop_scroll",
                "copy": "A sharper opener",
                "visual": "Product close-up",
                "healthScore": 87,
            },
            {
                "id": "seg-2",
                "type": "pain",
                "label": "Pain",
                "start": 3.0,
                "end": 8.0,
                "duration": 5.0,
                "goal": "problem_framing",
                "copy": "Everyday friction",
                "visual": "Office scene",
                "healthScore": 72,
            },
            {
                "id": "seg-3",
                "type": "cta",
                "label": "CTA",
                "start": 24.0,
                "end": 35.0,
                "duration": 11.0,
                "goal": "conversion",
                "copy": "Act now",
                "visual": "Offer screen",
                "healthScore": 68,
            },
        ],
        "rhythm": [
            {"second": 0, "cuts": 2, "emotion": 0.5},
            {"second": 5, "cuts": 4, "emotion": 0.6},
            {"second": 10, "cuts": 3, "emotion": 0.7},
            {"second": 15, "cuts": 5, "emotion": 0.9, "highlight": True},
            {"second": 20, "cuts": 3, "emotion": 0.75},
        ],
        "packaging": {
            "subtitleStyle": ["Bold sans-serif", "Warm white captions"],
            "transitions": ["Hard cut", "Push"],
            "overlays": ["Offer tag", "Product label"],
        },
        "health": {
            "hook_strength": 87,
            "product_exposure_timing": 62,
            "selling_point_proof": 58,
            "pacing_compactness": 81,
            "cta_persuasiveness": 67,
            "overall": 72,
        },
    }


def test_video_structure_accepts_frontend_aligned_fields() -> None:
    structure = VideoStructure.model_validate(valid_video_structure_payload())

    assert set(structure.model_dump().keys()) == {
        "meta",
        "script",
        "rhythm",
        "packaging",
        "health",
    }
    assert structure.script[0].type == "hook"
    assert structure.packaging.subtitleStyle[0] == "Bold sans-serif"


def test_video_structure_rejects_legacy_structure_field_names() -> None:
    legacy_payload = {
        "script_structure": [],
        "rhythm_structure": [],
        "packaging_structure": {},
        "health_scores": {},
    }

    with pytest.raises(ValidationError):
        VideoStructure.model_validate(legacy_payload)


@pytest.mark.parametrize("progress", [-1, 101])
def test_task_progress_rejects_out_of_range_progress(progress: int) -> None:
    with pytest.raises(ValidationError):
        TaskProgress(status="processing", progress=progress, stage="Invalid")


def test_task_progress_uses_standard_status_values() -> None:
    progress = TaskProgress(status="completed", progress=100, stage="Done")

    assert progress.status == "completed"
    with pytest.raises(ValidationError):
        TaskProgress(status="done", progress=100, stage="Done")
