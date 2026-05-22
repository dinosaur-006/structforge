from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import httpx

from config import Settings


def transcribe_video(source_path: Path, job_id: str, settings: Settings) -> dict[str, Any]:
    audio_path = settings.upload_dir / job_id / "audio.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    extract_result = subprocess.run(
        [
            settings.ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            "16000",
        str(audio_path),
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)
    if extract_result.returncode != 0:
        return {"asr_status": "failed", "segments": [], "error": "Audio extraction failed"}

    whisper_result = _try_whisperx(audio_path, settings)
    if whisper_result is not None:
        return whisper_result

    volcano_result = _try_volcano_asr(audio_path, settings)
    if volcano_result is not None:
        return volcano_result

    return {"asr_status": "failed", "segments": [], "error": "No ASR provider succeeded"}


def _try_whisperx(audio_path: Path, settings: Settings) -> dict[str, Any] | None:
    try:
        import whisperx  # type: ignore
    except ImportError:
        return None

    try:
        model = whisperx.load_model(settings.whisperx_model, device="cpu")
        result = model.transcribe(str(audio_path))
        segments = result.get("segments", [])
        return {"asr_status": "completed", "provider": "whisperx", "segments": segments}
    except Exception as exc:
        return {"asr_status": "failed", "provider": "whisperx", "segments": [], "error": str(exc)}


def _try_volcano_asr(audio_path: Path, settings: Settings) -> dict[str, Any] | None:
    if not settings.volcano_asr_endpoint or not settings.volcano_asr_api_key:
        return None

    try:
        with audio_path.open("rb") as handle:
            response = httpx.post(
                settings.volcano_asr_endpoint,
                headers={"Authorization": f"Bearer {settings.volcano_asr_api_key}"},
                files={"audio": ("audio.wav", handle, "audio/wav")},
                timeout=60,
            )
        response.raise_for_status()
        payload = response.json()
        return {
            "asr_status": "completed",
            "provider": "volcano",
            "segments": payload.get("segments", []),
        }
    except Exception as exc:
        return {"asr_status": "failed", "provider": "volcano", "segments": [], "error": str(exc)}
