"""Speech transcription using Volcano BigModel ASR (primary) or WhisperX (fallback)."""

from __future__ import annotations

import base64
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from config import Settings

BIGMODEL_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
BIGMODEL_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"


def transcribe_video(source_path: Path, job_id: str, settings: Settings) -> dict[str, Any]:
    """Transcribe video audio. Tries Volcano BigModel first, then WhisperX."""

    # Extract WAV audio from video.
    audio_path = settings.upload_dir / job_id / "audio.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    extract_result = subprocess.run(
        [settings.ffmpeg_path, "-y", "-i", str(source_path),
         "-ac", "1", "-ar", "16000", str(audio_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if extract_result.returncode != 0:
        return {"asr_status": "failed", "text": "", "segments": [], "error": "Audio extraction failed"}

    # Try Volcano BigModel ASR.
    if settings.volcano_asr_api_key:
        volcano_result = _try_volcano_bigmodel(audio_path, settings)
        if volcano_result is not None:
            import sys
            txt = volcano_result.get("text", "")
            sys.stderr.write(f"[ASR] ✅ Success! Text ({len(txt)} chars): {txt[:100]}\n")
            sys.stderr.flush()
            return volcano_result
        else:
            import sys
            sys.stderr.write("[ASR] ❌ Volcano BigModel returned None (failed)\n")
            sys.stderr.flush()

    # Fallback: WhisperX.
    whisper_result = _try_whisperx(audio_path, settings)
    if whisper_result is not None:
        return whisper_result

    return {"asr_status": "failed", "text": "", "segments": [], "error": "No ASR provider succeeded"}


def _try_volcano_bigmodel(audio_path: Path, settings: Settings) -> dict[str, Any] | None:
    """Two-step Volcano BigModel ASR: submit audio → poll until complete → return segments."""
    try:
        audio_bytes = audio_path.read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

        # task_id = X-Api-Request-Id we generate (response body is empty per API docs)
        task_id = str(uuid.uuid4())

        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.volcano_asr_api_key,
            "X-Api-Resource-Id": settings.volcano_asr_resource_id,
            "X-Api-Request-Id": task_id,
            "X-Api-Sequence": "-1",
        }

        # Step 1: Submit (response body is empty — task_id is our X-Api-Request-Id).
        submit_body = {
            "user": {"uid": "structforge"},
            "audio": {
                "data": audio_b64,
                "format": "wav",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": False,
                "enable_ddc": False,
                "enable_speaker_info": False,
                "enable_channel_split": False,
                "show_utterances": True,
                "vad_segment": False,
                "sensitive_words_filter": "",
            },
        }

        resp = httpx.post(
            BIGMODEL_SUBMIT_URL,
            headers=headers,
            json=submit_body,
            timeout=30,
        )
        resp.raise_for_status()
        # Response body is empty per API docs — task_id is the X-Api-Request-Id we sent

        # Step 2: Poll using our task_id (max 60s).
        query_headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.volcano_asr_api_key,
            "X-Api-Resource-Id": settings.volcano_asr_resource_id,
            "X-Api-Request-Id": task_id,
        }
        for _ in range(20):
            time.sleep(3)
            query_resp = httpx.post(
                BIGMODEL_QUERY_URL,
                headers=query_headers,
                json={},
                timeout=15,
            )
            query_resp.raise_for_status()
            status_code = query_resp.headers.get("X-Api-Status-Code", "")
            query_payload = query_resp.json() if query_resp.content else {}

            if status_code == "20000000":  # Success
                result = query_payload.get("result", query_payload)
                utterances = result.get("utterances", [])
                if not utterances:
                    text = result.get("text", "")
                    if text:
                        utterances = [{"text": text, "start": 0, "end": 0, "words": []}]

                segments = _normalize_utterances(utterances)
                full_text = " ".join(s["text"] for s in segments)
                return {
                    "asr_status": "completed",
                    "provider": "volcano_bigmodel",
                    "text": full_text,
                    "segments": segments,
                }

            if status_code in ("20000001", "20000002"):
                continue  # Still processing / queued

            if status_code == "20000003":
                return {"asr_status": "completed", "provider": "volcano_bigmodel", "text": "", "segments": [], "error": "Silent audio — no speech detected"}

            # Any other code: failure
            import sys
            sys.stderr.write(f"[ASR] Query failed: status={status_code}, body={str(query_payload)[:200]}\n")
            sys.stderr.flush()
            return None

        return None

    except Exception:
        return None


def _try_whisperx(audio_path: Path, settings: Settings) -> dict[str, Any] | None:
    """Local WhisperX transcription."""
    try:
        import whisperx  # type: ignore
    except ImportError:
        return None

    try:
        model = whisperx.load_model(settings.whisperx_model, device="cpu")
        result = model.transcribe(str(audio_path))
        segments = result.get("segments", [])
        full_text = result.get("text", "") or " ".join(s.get("text", "") for s in segments)
        return {"asr_status": "completed", "provider": "whisperx", "text": full_text, "segments": segments}
    except Exception as exc:
        return {"asr_status": "failed", "provider": "whisperx", "text": "", "segments": [], "error": str(exc)}


def _normalize_utterances(utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize Volcano BigModel utterance format to common segment format."""
    segments: list[dict[str, Any]] = []
    for u in utterances:
        start = float(u.get("start_time", u.get("start", 0))) / 1000.0  # ms → s
        end = float(u.get("end_time", u.get("end", 0))) / 1000.0
        text = str(u.get("text", ""))
        if text.strip():
            segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text.strip(),
            })
    if not segments:
        # Try raw text fallback.
        full_text = " ".join(str(u.get("text", "")) for u in utterances).strip()
        if full_text:
            segments.append({"start": 0.0, "end": 0.0, "text": full_text})
    return segments
