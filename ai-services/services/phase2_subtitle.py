"""Phase 2: Subtitle system — TTS synthesis, keyword extraction, hard-subtitle handling."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from services.optimization_models import StructureSegment, SubtitleEvent, SubtitleType

# ── TTS ──

TTS_SSE_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
VOICE_MAP = {"zh_female_vivid": "zh_female_cancan_mars_bigtts", "zh_male": "zh_male_ahu_conversation_wvae_bigtts"}


class TTSResult:
    def __init__(self, audio_path: str, word_timestamps: list[dict[str, Any]]) -> None:
        self.audio_path = audio_path
        self.word_timestamps = word_timestamps


class TTSGenerator:
    def __init__(self, api_key: str | None = None, voice: str = "zh_female_vivid") -> None:
        self.api_key = api_key
        self.speaker = VOICE_MAP.get(voice, voice)
        self._available = bool(api_key)

    def synthesize(self, script: str, output_dir: str | Path | None = None) -> TTSResult | None:
        """Synthesize TTS audio and return timestamps."""
        if not self._available or not script.strip():
            return None

        out_dir = Path(output_dir or tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "tts_output.mp3"

        try:
            resp = httpx.post(
                TTS_SSE_URL,
                headers={"X-Api-Key": self.api_key, "X-Api-Resource-Id": "seed-tts-1.0"},
                json={
                    "user": {"uid": "structforge"},
                    "req_params": {
                        "text": script.strip(),
                        "speaker": self.speaker,
                        "audio_params": {"format": "mp3", "sample_rate": 24000},
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            audio_chunks: list[bytes] = []
            for line in resp.text.split("\n"):
                if line.startswith("data:"):
                    payload_str = line[5:].strip()
                    if payload_str and payload_str != "[DONE]":
                        try:
                            data = json.loads(payload_str)
                            b64 = data.get("data", "")
                            if b64:
                                import base64
                                audio_chunks.append(base64.b64decode(b64))
                        except Exception:
                            continue
            if audio_chunks:
                audio_path.write_bytes(b"".join(audio_chunks))
                duration = self._probe_duration(audio_path)
                timestamps = self._estimate_timestamps(script, duration)
                return TTSResult(str(audio_path), timestamps)
        except Exception:
            pass
        return None

    def _probe_duration(self, path: Path) -> float:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return float(r.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

    def _estimate_timestamps(self, text: str, total_duration: float) -> list[dict[str, Any]]:
        """Estimate per-character timestamps when API doesn't provide them."""
        chars = len(text.replace(" ", ""))
        if chars == 0 or total_duration <= 0:
            return []
        per_char = total_duration / chars
        return [{"char": c, "start": round(i * per_char, 3), "end": round((i + 1) * per_char, 3)} for i, c in enumerate(text) if c.strip()]


class SubtitleExtractor:
    """Extract concise on-screen keywords from TTS scripts."""

    def extract(self, script: str, segment_type: str) -> str:
        """Extract screen keywords based on segment type rules."""
        if segment_type == "hook":
            return script[:8] if len(script) > 8 else script
        if segment_type == "cta":
            # Price + action — take last 10 chars or keywords
            keywords = ["点击", "下单", "购买", "优惠", "限时", "手慢", "链接", "价格"]
            for kw in keywords:
                if kw in script:
                    idx = script.index(kw)
                    return script[max(0, idx - 4): idx + 8]
            return script[-12:] if len(script) > 12 else script
        if segment_type in ("proof", "compare"):
            return script[:15] if len(script) > 15 else script
        # Default: first meaningful phrase
        return script[:15] if len(script) > 15 else script


def handle_hardcoded_subtitles(video_path: str, ocr_regions: list[dict[str, Any]], user_choice: str) -> dict[str, Any]:
    """Handle original video hard-coded subtitles."""
    result = {"action": "none", "processed_path": video_path}
    if user_choice == "keep_style":
        # Apply delogo to remove original subtitles at detected regions
        output = str(Path(video_path).with_stem(Path(video_path).stem + "_delogo"))
        filters = []
        for region in ocr_regions[:3]:
            x, y, w, h = region.get("x", 0), region.get("y", 1600), region.get("w", 1080), region.get("h", 320)
            filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:show=0")
        if filters:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-vf", ",".join(filters), "-c:a", "copy", output],
                capture_output=True, check=False,
            )
            result["processed_path"] = output
            result["action"] = "delogo_applied"
    elif user_choice == "replace_all":
        result["action"] = "replace_all"
        result["processed_path"] = ""
    return result
