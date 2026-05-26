from __future__ import annotations

import html
import subprocess
from pathlib import Path
from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript
from services.gap_filler import render_packaging_card


RESOLUTIONS = {
    "1080p": (1080, 1920),
    "720p": (720, 1280),
}


class CompositorError(RuntimeError):
    pass


class Compositor:
    def __init__(self, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def render(self, *, job_id: str, project_id: str, version: str, resolution: str, script_version: str | None = None) -> None:
        warnings: list[str] = []
        try:
            self.repository.update_render_job(job_id, status="processing", progress=5)
            script_payload = (
                self.repository.get_script_version(project_id, script_version)
                if script_version
                else self.repository.get_project_script(project_id)
            )
            if not script_payload:
                raise CompositorError("Project has no FinalScript")
            script = FinalScript.model_validate(script_payload)
            assets = {asset["id"]: asset for asset in self.repository.list_assets(project_id)}
            width, height = RESOLUTIONS.get(resolution, RESOLUTIONS["1080p"])
            work_dir = self.settings.output_dir / project_id / f".work-{job_id}"
            output_dir = self.settings.output_dir / project_id
            work_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            segments = _segments_for_version(script, version)
            if not segments:
                raise CompositorError("FinalScript has no renderable segments")

            segment_files: list[Path] = []
            for index, segment in enumerate(segments):
                self.repository.update_render_job(job_id, progress=10 + (index / max(len(segments), 1)) * 60)
                segment_path = work_dir / f"segment_{index:03d}.mp4"
                ass_path = work_dir / f"segment_{index:03d}.ass"
                output_duration = _output_duration(segment.duration, version, segment.type)
                ass_path.write_text(_ass_for_segment(segment, version, output_duration), encoding="utf-8")
                asset = assets.get(segment.asset_id) if segment.asset_id else None
                source_path = Path(asset["file_path"]) if asset and asset.get("file_path") else None
                if source_path is None or not source_path.exists():
                    if segment.asset_id:
                        warnings.append(f"missing asset {segment.asset_id}, used placeholder")
                    if segment.source == "packaging":
                        render_card_path = work_dir / f"segment_{index:03d}_packaging.png"
                        render_packaging_card(
                            render_card_path,
                            title=segment.type.upper(),
                            body=segment.script,
                            card_type=segment.type,
                            font_path=self.settings.packaging_font_path,
                        )
                        warnings.append(f"render-time packaging card used for segment {segment.id}")
                        command = build_image_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=render_card_path,
                            output_path=segment_path,
                            ass_path=ass_path,
                            duration=max(segment.duration, 0.5),
                            width=width,
                            height=height,
                            version=version,
                            segment_type=segment.type,
                        )
                    else:
                        command = build_placeholder_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            output_path=segment_path,
                            ass_path=ass_path,
                            duration=max(segment.duration, 0.5),
                            width=width,
                            height=height,
                            version=version,
                            segment_type=segment.type,
                        )
                elif asset["type"] == "image":
                    if source_path.suffix.lower() == ".svg":
                        regenerated_path = source_path.with_suffix(".png")
                        analysis = asset.get("analysis") or {}
                        render_packaging_card(
                            regenerated_path,
                            title=asset.get("name") or segment.type,
                            body=str(analysis.get("ocr_text") or segment.script),
                            card_type=segment.type,
                            font_path=self.settings.packaging_font_path,
                        )
                        warnings.append(f"regenerated legacy packaging asset {segment.asset_id} as png")
                        command = build_image_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=regenerated_path,
                            output_path=segment_path,
                            ass_path=ass_path,
                            duration=max(segment.duration, 0.5),
                            width=width,
                            height=height,
                            version=version,
                            segment_type=segment.type,
                        )
                    else:
                        command = build_image_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=source_path,
                            output_path=segment_path,
                            ass_path=ass_path,
                            duration=max(segment.duration, 0.5),
                            width=width,
                            height=height,
                            version=version,
                            segment_type=segment.type,
                        )
                else:
                    command = build_video_command(
                        ffmpeg_path=self.settings.ffmpeg_path,
                        input_path=source_path,
                        output_path=segment_path,
                        ass_path=ass_path,
                        duration=max(segment.duration, 0.5),
                        width=width,
                        height=height,
                        version=version,
                        segment_type=segment.type,
                        has_audio=_has_audio_stream(source_path, self.settings.ffprobe_path),
                    )
                _run(command)
                segment_files.append(segment_path)

            self.repository.update_render_job(job_id, progress=80, warnings=warnings)
            concat_file = work_dir / "concat.txt"
            concat_file.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_files), encoding="utf-8")
            output_path = output_dir / f"{version}.mp4"
            _run([
                self.settings.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ])
            self.repository.update_render_job(
                job_id,
                status="completed",
                progress=100,
                output_path=f"/outputs/{project_id}/{version}.mp4",
                warnings=warnings,
            )
        except Exception as exc:
            self.repository.update_render_job(job_id, status="failed", progress=100, error=str(exc), warnings=warnings)


def build_placeholder_command(
    *,
    ffmpeg_path: str,
    output_path: Path,
    ass_path: Path,
    duration: float,
    width: int,
    height: int,
    version: str,
    segment_type: str,
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type)
    return [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={width}x{height}:r=30:d={output_duration:.3f}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        f"{output_duration:.3f}",
        "-vf",
        filters,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]


def build_image_command(
    *,
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    ass_path: Path,
    duration: float,
    width: int,
    height: int,
    version: str,
    segment_type: str,
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type)
    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-i",
        str(input_path),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        f"{output_duration:.3f}",
        "-vf",
        filters,
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]


def build_video_command(
    *,
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    ass_path: Path,
    duration: float,
    width: int,
    height: int,
    version: str,
    segment_type: str,
    has_audio: bool = False,
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type)
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
    ]
    if not has_audio:
        command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
    command.extend([
        "-t",
        f"{output_duration:.3f}",
        "-vf",
        filters,
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ])
    return command


def _version_filters(width: int, height: int, ass_path: Path, version: str, segment_type: str) -> str:
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
    ]
    if version == "strong_hook" and segment_type == "hook":
        filters.extend(["setpts=0.77*PTS", "zoompan=z='min(zoom+0.0015,1.08)':d=1", "eq=contrast=1.12"])
    if version == "strong_conversion" and segment_type == "cta":
        filters.extend(["tpad=stop_mode=clone:stop_duration=2", "drawbox=x=60:y=80:w=520:h=150:color=white@0.88:t=fill"])
    filters.append(f"subtitles='{_ffmpeg_filter_path(ass_path)}'")
    filters.append("format=yuv420p")
    return ",".join(filters)


def _segments_for_version(script: FinalScript, version: str):
    if version != "safe_fix":
        return script.segments
    filtered = [segment for segment in script.segments if segment.asset_id or segment.type in {"hook", "cta"}]
    return filtered or script.segments


def _ass_for_segment(segment: Any, version: str, duration: float | None = None) -> str:
    font_size = 68 if version == "strong_hook" and segment.type == "hook" else 52
    if version == "safe_fix":
        font_size = 44
    text = _ass_text(segment.script)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00F5F5F5,&H000000FF,&H00181818,&H66000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{_ass_time(duration if duration is not None else segment.duration)},Default,,0,0,0,,{text}
"""


def _ass_text(value: str) -> str:
    escaped = html.escape(value, quote=False).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    if len(escaped) > 20:
        midpoint = len(escaped) // 2
        escaped = escaped[:midpoint] + r"\N" + escaped[midpoint:]
    return escaped


def _ass_time(seconds: float) -> str:
    total_centiseconds = int(max(seconds, 0.5) * 100)
    centiseconds = total_centiseconds % 100
    total_seconds = total_centiseconds // 100
    secs = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _ffmpeg_filter_path(path: Path) -> str:
    return path.as_posix().replace(":", "\\:")


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "FFmpeg command failed").strip()
        raise CompositorError(message[-1200:])


def _output_duration(duration: float, version: str, segment_type: str) -> float:
    if version == "strong_conversion" and segment_type == "cta":
        return max(duration, 0.5) + 2.0
    return max(duration, 0.5)


def _has_audio_stream(input_path: Path, ffprobe_path: str) -> bool:
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0 and bool(result.stdout.strip())
