"""Audio waveform extraction for frontend visualization.

Uses FFmpeg to extract amplitude data and segment labels (TTS/BGM/silence).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def get_waveform_data(
    video_path: str | Path,
    *,
    sample_count: int = 300,
    ffmpeg_path: str = "ffmpeg",
) -> dict[str, Any] | None:
    """Extract waveform amplitude data from a video file.

    Returns a dict with:
      - data: list[float] — normalized amplitudes (0.0–1.0), sample_count points
      - duration: float — total audio duration in seconds
      - labels: list[dict] — segment labels for TTS/BGM/silence regions
    """
    p = Path(video_path)
    if not p.exists():
        return None

    try:
        # Extract raw audio samples as 16-bit PCM mono
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        result = subprocess.run(
            [
                ffmpeg_path, "-y", "-v", "error",
                "-i", str(p),
                "-ac", "1", "-ar", "8000",
                "-f", "s16le",
                str(tmp_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not tmp_path.exists():
            return None

        raw = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)

        if len(raw) < 16:
            return None

        # Convert raw PCM to amplitude values
        import struct
        samples = []
        for i in range(0, len(raw) - 1, 2):
            try:
                val = struct.unpack("<h", raw[i:i+2])[0]
                samples.append(abs(val) / 32768.0)
            except struct.error:
                break

        if not samples:
            return None

        # Downsample to desired count using max pooling
        step = max(1, len(samples) // sample_count)
        data: list[float] = []
        for i in range(0, len(samples), step):
            chunk = samples[i:i+step]
            data.append(round(max(chunk), 4))

        data = data[:sample_count]

        # Estimate audio duration
        duration = len(samples) / 8000.0

        # Detect speech/silence segments (simple threshold-based)
        labels: list[dict[str, Any]] = []
        threshold = 0.03
        in_speech = False
        speech_start = 0.0
        for i, amp in enumerate(data):
            t = (i / len(data)) * duration
            if amp > threshold and not in_speech:
                in_speech = True
                speech_start = t
            elif amp <= threshold and in_speech:
                in_speech = False
                if t - speech_start > 0.3:  # minimum 300ms segment
                    labels.append({
                        "start": round(speech_start, 2),
                        "end": round(t, 2),
                        "type": "speech",
                    })
        if in_speech and duration - speech_start > 0.3:
            labels.append({
                "start": round(speech_start, 2),
                "end": round(duration, 2),
                "type": "speech",
            })

        return {
            "data": data,
            "duration": round(duration, 2),
            "labels": labels,
        }
    except Exception:
        return None
