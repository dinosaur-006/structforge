from __future__ import annotations

import json
from pathlib import Path

import httpx

from config import Settings
from services.asset_analyzer import _analyze_image
from services.vision import analyze_frames


class FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "frames": [
                                    {
                                        "index": 1,
                                        "description": "人物在户外佩戴降噪耳机",
                                        "ocr": ["Bose QC Ultra"],
                                        "tags": ["产品特写", "人物", "户外场景"],
                                        "dominant_colors": ["green"],
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


def test_analyze_frames_reuses_lite_multimodal_llm_configuration(tmp_path: Path, monkeypatch) -> None:
    frame_path = tmp_path / "frame.jpg"
    frame_path.write_bytes(b"jpeg-content")
    settings = Settings(
        doubao_llm_endpoint="https://example.invalid/chat/completions",
        doubao_llm_api_key="test-only-key",
        doubao_llm_model="doubao-seed-2-0-lite",
        doubao_vision_endpoint=None,
        doubao_vision_api_key=None,
    )
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int) -> FakeResponse:
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("services.vision.httpx.post", fake_post)

    result = analyze_frames([frame_path], settings)

    assert result["vision_status"] == "completed"
    assert result["frames"][0]["tags"] == ["产品特写", "人物", "户外场景"]
    assert captured["url"] == "https://example.invalid/chat/completions"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "doubao-seed-2-0-lite"
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_image_analysis_uses_visual_description_for_role_tags(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "asset.jpg"
    image_path.write_bytes(b"jpeg-content")
    monkeypatch.setattr(
        "services.asset_analyzer.analyze_frames",
        lambda paths, settings: {
            "vision_status": "completed",
            "frames": [{"description": "耳机产品特写，展示降噪功能", "ocr": [], "tags": ["耳机"]}],
        },
    )

    analysis = _analyze_image(image_path, Settings(doubao_llm_endpoint=None, doubao_llm_api_key=None))

    assert "产品特写" in analysis["tags"]


def test_visual_request_retries_transient_disconnect(tmp_path: Path, monkeypatch) -> None:
    frame_path = tmp_path / "frame.jpg"
    frame_path.write_bytes(b"jpeg-content")
    settings = Settings(
        doubao_llm_endpoint="https://example.invalid/chat/completions",
        doubao_llm_api_key="test-only-key",
        doubao_llm_model="doubao-seed-2-0-lite",
        llm_max_attempts=2,
    )
    attempts = 0

    def fake_post(*args, **kwargs) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.RemoteProtocolError("disconnected")
        return FakeResponse()

    monkeypatch.setattr("services.vision.httpx.post", fake_post)

    result = analyze_frames([frame_path], settings)

    assert attempts == 2
    assert result["vision_status"] == "completed"
