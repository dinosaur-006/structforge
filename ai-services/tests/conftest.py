from __future__ import annotations

import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


@pytest.fixture(autouse=True)
def disable_external_services_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "STRUCTFORGE_DOUBAO_LLM_ENDPOINT",
        "STRUCTFORGE_DOUBAO_LLM_API_KEY",
        "STRUCTFORGE_DOUBAO_VISION_ENDPOINT",
        "STRUCTFORGE_DOUBAO_VISION_API_KEY",
        "STRUCTFORGE_VOLCANO_ASR_ENDPOINT",
        "STRUCTFORGE_VOLCANO_ASR_API_KEY",
        "STRUCTFORGE_JIMENG_IMAGE_ENDPOINT",
        "STRUCTFORGE_JIMENG_IMAGE_API_KEY",
    ):
        monkeypatch.setenv(key, "")
