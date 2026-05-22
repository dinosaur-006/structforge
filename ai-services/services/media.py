from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from config import Settings


class MediaToolError(RuntimeError):
    pass


def _resolve_executable(command: str) -> str:
    if Path(command).exists():
        return command
    resolved = shutil.which(command)
    if resolved:
        return resolved
    raise MediaToolError(f"Required media tool is not available: {command}")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _parse_frame_rate(raw: str | None) -> float:
    if not raw:
        return 0.0
    if "/" in raw:
        numerator, denominator = raw.split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else 0.0
    return float(raw)


def probe_video(source_path: Path, settings: Settings) -> dict[str, Any]:
    ffprobe = _resolve_executable(settings.ffprobe_path)
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,codec_name:format=duration",
        "-of",
        "json",
        str(source_path),
    ]
    completed = _run(command)
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr.strip() or "ffprobe failed to inspect video")

    payload = json.loads(completed.stdout)
    stream = payload.get("streams", [{}])[0]
    format_info = payload.get("format", {})
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    return {
        "duration": float(format_info.get("duration") or 0.0),
        "resolution": f"{width}x{height}" if width and height else "unknown",
        "width": width,
        "height": height,
        "frame_rate": _parse_frame_rate(stream.get("avg_frame_rate")),
        "codec": stream.get("codec_name") or "unknown",
    }


def detect_scenes(source_path: Path, duration: float, settings: Settings) -> list[dict[str, int]]:
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
    except ImportError:
        return [_whole_video_scene(duration)]

    video = open_video(str(source_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=settings.scene_threshold))
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()
    if not scene_list:
        return [_whole_video_scene(duration)]

    scenes: list[dict[str, int]] = []
    for start_time, end_time in scene_list:
        start_ms = int(start_time.get_seconds() * 1000)
        end_ms = int(end_time.get_seconds() * 1000)
        scenes.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
            }
        )
    return scenes or [_whole_video_scene(duration)]


def _whole_video_scene(duration: float) -> dict[str, int]:
    duration_ms = int(max(duration, 0.0) * 1000)
    return {"start_ms": 0, "end_ms": duration_ms, "duration_ms": duration_ms}


def keyframe_times(scenes: list[dict[str, int]], duration: float, max_frames: int) -> list[float]:
    times: set[float] = set()
    for scene in scenes:
        midpoint_ms = scene["start_ms"] + scene["duration_ms"] / 2
        times.add(round(midpoint_ms / 1000, 2))

    min_frames = min(max(int(duration), 1), max_frames)
    second = 0
    while len(times) < min_frames and second <= int(duration):
        times.add(float(second))
        second += 1

    return sorted(t for t in times if 0 <= t <= max(duration, 0.0))[:max_frames]


def extract_keyframes(source_path: Path, job_id: str, scenes: list[dict[str, int]], duration: float, settings: Settings) -> list[Path]:
    ffmpeg = _resolve_executable(settings.ffmpeg_path)
    frame_dir = settings.upload_dir / job_id / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []

    for index, second in enumerate(keyframe_times(scenes, duration, settings.max_keyframes), start=1):
        output_path = frame_dir / f"frame_{index:04d}.jpg"
        command = [
            ffmpeg,
            "-y",
            "-ss",
            f"{second:.2f}",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        completed = _run(command)
        if completed.returncode == 0 and output_path.exists():
            frames.append(output_path)

    if not frames:
        raise MediaToolError("Failed to extract keyframes from video")
    return frames
