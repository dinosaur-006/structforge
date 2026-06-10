"""BGM engine: beat detection and audio mixing for video composition.

Requires librosa (optional) for beat detection. Falls back to simple
BGM overlay when librosa is not available.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


class BGMEngine:
    """Select and mix background music into the video composition."""

    # Built-in BGM categories with default track names.
    CATEGORIES = {
        "energetic": {"label": "高能量", "description": "适合快节奏带货视频"},
        "corporate": {"label": "专业商务", "description": "适合产品介绍与数据展示"},
        "inspirational": {"label": "励志感动", "description": "适合品牌故事与情感内容"},
        "minimal": {"label": "极简背景", "description": "低调不喧宾夺主的氛围音乐"},
    }

    # ── Emotional resonance → BGM category mapping ──
    EMOTION_BGM_MAP: dict[str, str] = {
        "高能炸裂": "energetic",
        "紧迫焦虑": "energetic",
        "温馨治愈": "minimal",
        "精致共鸣": "inspirational",
        "干货信赖": "corporate",
        "专业亲切": "corporate",
        "沉浸式生活美学": "minimal",
        "科技未来感": "corporate",
        "时尚潮流": "energetic",
        "治愈解压": "minimal",
    }

    @classmethod
    def bgm_for_emotion(cls, emotional_resonance: str) -> str:
        """Return the recommended BGM category for a given emotional resonance."""
        return cls.EMOTION_BGM_MAP.get(emotional_resonance, "minimal")

    def __init__(
        self,
        bgm_dir: str | Path | None = None,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ) -> None:
        self._bgm_dir = Path(bgm_dir) if bgm_dir else None
        self.ffmpeg_path = shutil.which(ffmpeg_path) or ffmpeg_path
        self.ffprobe_path = shutil.which(ffprobe_path) or ffprobe_path

        # Check for librosa availability.
        self._has_librosa = False
        try:
            import librosa  # noqa: F401
            self._has_librosa = True
        except ImportError:
            pass

    def list_tracks(self) -> list[dict[str, Any]]:
        """Return available BGM tracks. Generates ambient tone if no tracks exist."""
        tracks: list[dict[str, Any]] = []
        if self._bgm_dir and self._bgm_dir.exists():
            for file in sorted(self._bgm_dir.glob("*.mp3")):
                duration = self._probe_duration(file)
                tracks.append({
                    "id": file.stem,
                    "name": file.stem.replace("_", " ").title(),
                    "path": str(file),
                    "duration": duration,
                    "category": self._guess_category(file.stem),
                })
        return tracks

    def generate_ambient(self, output_path: str | Path, duration: float = 30.0) -> str | None:
        """Generate a simple ambient tone via FFmpeg if no BGM files exist."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Generate a gentle ambient pad using FFmpeg sine wave + lowpass.
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=220:duration={duration:.1f}",
            "-f", "lavfi",
            "-i", f"sine=frequency=330:duration={duration:.1f}",
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first,volume=0.08,lowpass=f=600",
            str(out),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode == 0 and out.exists():
                return str(out)
        except Exception:
            pass
        return None

    def detect_beats(self, track_path: str | Path, segment_duration: float = 0.0, pace: str = "正常") -> list[float]:
        """Return beat timestamps in seconds.

        Uses librosa for precision when available. Falls back to adaptive BPM
        grid based on segment pace (快=140, 正常=120, 慢=100).
        """
        if self._has_librosa:
            try:
                import librosa
                y, sr = librosa.load(str(track_path), sr=22050, duration=segment_duration if segment_duration > 0 else None)
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                beat_times = librosa.frames_to_time(beat_frames, sr=sr)
                return [float(t) for t in beat_times]
            except Exception:
                pass

        # Adaptive BPM based on pace
        bpm_map = {"快": 140, "正常": 120, "慢": 100}
        bpm = bpm_map.get(pace, 120)
        beat_interval = 60.0 / bpm
        dur = segment_duration if segment_duration > 0 else 30.0
        return [round(i * beat_interval, 2) for i in range(int(dur / beat_interval) + 1)]

    def mix_command(
        self,
        *,
        input_video: str | Path,
        bgm_path: str | Path,
        output_video: str | Path,
        volume: float = 0.25,
        duration: float = 0.0,
    ) -> list[str]:
        """Return FFmpeg command to mix BGM into video.

        Handles videos with NO existing audio stream by generating a silent
        track first, so BGM is always audible.
        """
        vol_filter = f"volume={max(0.0, min(volume, 1.0)):.2f}"
        inputs = [
            str(self.ffmpeg_path), "-y",
            "-i", str(input_video),
            "-stream_loop", "-1",
            "-i", str(bgm_path),
        ]
        if duration > 0:
            inputs.extend(["-t", f"{duration:.3f}"])

        # If input video has no audio stream, generate a silent one.
        # [0:a] won't exist → use anullsrc as dummy audio source.
        has_audio = self._probe_has_audio(input_video)
        if has_audio:
            filters = f"[1:a]{vol_filter}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2"
        else:
            filters = f"[1:a]{vol_filter},apad[bgm];anullsrc=r=44100:cl=stereo[sl];[sl][bgm]amix=inputs=2:duration=first:dropout_transition=2"

        return [
            *inputs,
            "-filter_complex", filters,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_video),
        ]

    def _probe_has_audio(self, path: str | Path) -> bool:
        """Check whether a video file has at least one audio stream."""
        try:
            result = subprocess.run(
                [self.ffprobe_path, "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=10,
            )
            return "audio" in result.stdout.lower()
        except Exception:
            # ffprobe not available or file unreadable — assume no audio
            return False

    def _probe_duration(self, path: Path) -> float:
        result = subprocess.run(
            [self.ffprobe_path, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        try:
            return float(result.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

    def _guess_category(self, stem: str) -> str:
        lower = stem.lower()
        if any(w in lower for w in ["energetic", "upbeat", "fast", "rock", "electronic"]):
            return "energetic"
        if any(w in lower for w in ["corporate", "business", "tech", "clean"]):
            return "corporate"
        if any(w in lower for w in ["inspire", "epic", "cinematic", "emotional"]):
            return "inspirational"
        return "minimal"

    def _uniform_beats(self, duration: float, pace: str = "正常") -> list[float]:
        """Adaptive beat grid based on segment pace. Replaced by detect_beats(pace=...)."""
        return self.detect_beats("", duration, pace=pace)
