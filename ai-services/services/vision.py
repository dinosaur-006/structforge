from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from config import Settings


def analyze_frames(frame_paths: list[Path], settings: Settings) -> dict[str, Any]:
    if not settings.doubao_vision_endpoint or not settings.doubao_vision_api_key:
        return {
            "vision_status": "skipped",
            "frames": [_placeholder_frame(index, path) for index, path in enumerate(frame_paths, start=1)],
        }

    frames: list[dict[str, Any]] = []
    for batch_start in range(0, len(frame_paths), 5):
        batch = frame_paths[batch_start : batch_start + 5]
        frames.extend(_send_vision_batch(batch, batch_start, settings))
    return {"vision_status": "completed", "frames": frames}


def _send_vision_batch(batch: list[Path], batch_start: int, settings: Settings) -> list[dict[str, Any]]:
    payload = {
        "frames": [
            {
                "index": batch_start + offset + 1,
                "image_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
            for offset, path in enumerate(batch)
        ]
    }
    response = httpx.post(
        settings.doubao_vision_endpoint or "",
        headers={"Authorization": f"Bearer {settings.doubao_vision_api_key}"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("frames", [])


def _placeholder_frame(index: int, path: Path) -> dict[str, Any]:
    return {
        "index": index,
        "path": str(path),
        "description": "Key product or scene frame awaiting visual model analysis",
        "ocr": [],
        "tags": ["placeholder"],
        "dominant_colors": [],
    }
