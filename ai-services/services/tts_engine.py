"""TTS engine using Volcano SeedTTS HTTP SSE unidirectional API.

Streams audio via SSE (Server-Sent Events). One HTTP POST per segment.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx


TTS_SSE_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"

# Available voices from Volcano SeedTTS 2.0
VOICES: dict[str, str] = {
    "zh_female_qingxin": "zh_female_cancan_mars_bigtts",
    "zh_female_wenrou": "zh_female_shuangkuaisisi_moon_bigtts",
    "zh_male_chenwen": "zh_male_ahu_conversation_wvae_bigtts",
    "zh_female_tianmei": "zh_female_vv_uranus_bigtts",
}


class TTSEngine:
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        voice: str = "zh_female_qingxin",
        speed: float = 1.0,
        resource_id: str = "seed-tts-1.0",
        ffmpeg_path: str = "ffmpeg",
        inference_mode: str = "api",
    ) -> None:
        self.endpoint = endpoint or TTS_SSE_URL
        self.api_key = api_key
        # Map short voice name to Volcano speaker ID.
        self.speaker = VOICES.get(voice, voice)
        self.speed = max(0.5, min(speed, 2.0))
        self.resource_id = resource_id
        self.ffmpeg_path = shutil.which(ffmpeg_path) or ffmpeg_path
        self.inference_mode = inference_mode  # "api" | "local"
        self._configured = bool(api_key) or inference_mode == "local"

    @property
    def available(self) -> bool:
        return self._configured

    def synthesize(self, text: str, output_path: Path, target_duration: float = 0.0) -> bool:
        """Generate TTS audio. Returns True on success.

        Routes to Edge TTS (local, free) or Volcano API based on inference_mode.
        When target_duration is provided, calculates required speed.
        """
        if not text.strip():
            return False
        if self.inference_mode == "local":
            return self._synthesize_local(text, output_path, target_duration)
        if not self._configured:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ── Dynamic speed based on text length vs target duration ──
        effective_speed = self.speed
        if target_duration > 0 and len(text) > 0:
            chars_per_sec_normal = 4.5  # Chinese TTS baseline
            normal_duration = len(text) / chars_per_sec_normal
            required_speed = normal_duration / target_duration
            effective_speed = min(max(required_speed, 0.8), 1.5)
        # Speech rate: map 0.5–2.0 speed to Volcano's -50..100 range.
        # speed=1.0 → 0, speed=2.0 → 50, speed=0.5 → -25
        speech_rate = int((effective_speed - 1.0) * 50)

        body = {
            "user": {"uid": "structforge"},
            "req_params": {
                "text": text.strip(),
                "speaker": self.speaker,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000,
                    "speech_rate": speech_rate,
                },
            },
        }

        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "X-Api-Key": self.api_key,
                    "X-Api-Resource-Id": self.resource_id,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30,
            )
            response.raise_for_status()

            # SSE response: each "data:" line is a JSON object with base64 audio in "data" field.
            import base64, json
            audio_chunks: list[bytes] = []
            for line in response.text.split("\n"):
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[5:].strip()
                if not payload_str:
                    continue
                try:
                    payload = json.loads(payload_str)
                    b64 = payload.get("data", "")
                    if b64:
                        audio_chunks.append(base64.b64decode(b64))
                except Exception:
                    continue

            if not audio_chunks:
                # Fallback: raw response body.
                if response.content and len(response.content) > 100:
                    output_path.write_bytes(response.content)
                    return self._post_process(output_path, target_duration)
                return False

            output_path.write_bytes(b"".join(audio_chunks))
            return self._post_process(output_path, target_duration)

        except Exception:
            return False

    def _post_process(self, path: Path, target_duration: float) -> bool:
        """Stretch/compress audio to match target duration if needed."""
        if target_duration <= 0 or not path.exists():
            return True
        actual = self._probe_duration(path)
        if actual <= 0 or abs(actual - target_duration) < 0.3:
            return True
        tempo = actual / target_duration
        tempo = max(0.5, min(tempo, 2.0))
        tmp = path.with_suffix(".tmp.mp3")
        subprocess.run(
            [self.ffmpeg_path, "-y", "-i", str(path),
             "-filter:a", f"atempo={tempo:.2f}", str(tmp)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(path)
        return True

    def _probe_duration(self, path: Path) -> float:
        ffprobe = shutil.which("ffprobe") or "ffprobe"
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        try:
            return float(result.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

    def _synthesize_local(self, text: str, output_path: Path, target_duration: float = 0.0) -> bool:
        """Edge TTS — free, no API key, Windows built-in engine.

        Uses Microsoft Edge TTS via edge-tts package. Voice quality is
        comparable to Volcano TTS for Chinese narration.
        """
        try:
            import asyncio as _asyncio
            import edge_tts as _edge_tts
        except ImportError:
            return False

        # Voice mapping: our short names → Edge TTS voice IDs
        voice_map = {
            "zh_female_qingxin": "zh-CN-XiaoxiaoNeural",
            "zh_female_wenrou": "zh-CN-XiaoyiNeural",
            "zh_male_chenwen": "zh-CN-YunxiNeural",
            "zh_female_tianmei": "zh-CN-XiaohanNeural",
        }
        voice_id = voice_map.get(self.speaker, "zh-CN-XiaoxiaoNeural")

        # Speed → rate conversion for Edge TTS
        rate_map = {0.8: "-20%", 0.9: "-10%", 1.0: "+0%", 1.1: "+10%",
                     1.2: "+20%", 1.3: "+30%", 1.5: "+50%"}
        rate = rate_map.get(round(self.speed, 1), "+0%")

        async def _run():
            communicate = _edge_tts.Communicate(text, voice_id, rate=rate)
            await communicate.save(str(output_path))

        try:
            _asyncio.run(_run())
        except RuntimeError:
            # Already in an event loop
            import asyncio as _aio
            loop = _aio.get_event_loop()
            loop.run_until_complete(_run())

        if output_path.exists() and output_path.stat().st_size > 1000:
            return self._post_process(output_path, target_duration)
        return False
