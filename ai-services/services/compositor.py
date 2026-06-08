from __future__ import annotations

import html
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript
from services.gap_filler import render_packaging_card
from services.bgm_engine import BGMEngine
from services.tts_engine import TTSEngine
from services.video_generator import VideoGenerator, build_master_prompt
from services.animated_overlay import create_animated_overlay
from services.renderer_abstraction import RendererFactory, VideoRenderer


RESOLUTIONS = {
    "1080p": (1080, 1920),
    "720p": (720, 1280),
}


class CompositorError(RuntimeError):
    pass


def _validate_restructure_decision(script: FinalScript) -> None:
    if not any(segment.source == "reorder" for segment in script.segments):
        return
    metadata = script.metadata or {}
    if metadata.get("restructure_needed") is True and str(metadata.get("edit_reason") or "").strip():
        return
    raise CompositorError("脚本包含未经 AI 分析确认的结构重排，请重新生成脚本后再渲染。")


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
            _validate_restructure_decision(script)
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
                self.repository.update_render_job(
                    job_id,
                    progress=10 + (index / max(len(segments), 1)) * 60,
                    warnings=[f"渲染分镜 {index + 1}/{len(segments)}"],
                )
                segment_path = work_dir / f"segment_{index:03d}.mp4"
                ass_path = work_dir / f"segment_{index:03d}.ass"
                output_duration = _output_duration(segment.duration, version, segment.type)
                ass_path.write_text(_ass_for_segment(segment, version, output_duration), encoding="utf-8")
                asset = assets.get(segment.asset_id) if segment.asset_id else None
                source_path = Path(asset["file_path"]) if asset and asset.get("file_path") else None

                # ── TRACE: log every segment's render plan ──
                log.info(
                    "[TRACE] seg=%s type=%s source=%s has_asset=%s asset_type=%s src_path=%s",
                    segment.id, segment.type, getattr(segment, 'source', '?'),
                    bool(asset), asset.get("type") if asset else "none",
                    source_path.name if source_path else "none",
                )
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
                    analysis = asset.get("analysis") or {}
                    is_reference = analysis.get("reference_source") is True

                    # Reference video without user assets: render as clean card
                    # to avoid original subtitles/audio mismatch.
                    # Try shot-pool recombination first for reference clips.
                    shot_used = False
                    if is_reference and segment.source != "reorder":
                        shot_result = _find_shot_for_segment(
                            segment.type, segment.duration,
                            script.metadata.get("shot_pool", []),
                            source_path,
                        )
                        if shot_result:
                            shot_cmd = build_video_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                input_path=Path(shot_result["source"]),
                                output_path=segment_path,
                                ass_path=ass_path,
                                duration=shot_result["duration_s"],
                                width=width, height=height,
                                version=version, segment_type=segment.type,
                                has_audio=False,
                                start_seconds=shot_result["start_s"],
                            )
                            _run(shot_cmd)
                            if segment_path.exists() and segment_path.stat().st_size > 0:
                                shot_used = True
                                warnings.append(f"recombined shot for segment {segment.id} from pool")

                    # Try AI video generation before falling back to cards.
                    if not shot_used and is_reference and segment.source != "reorder":
                        video_gen = VideoGenerator(
                            api_key=self.settings.doubao_image_api_key,
                            model=self.settings.doubao_video_model,
                        )
                        if video_gen.available:
                            gen_path = work_dir / f"segment_{index:03d}_aivideo.mp4"
                            visual_text = (getattr(segment, 'visual', '') or segment.script or "").strip()
                            seg_data = segment.model_dump(mode="json") if hasattr(segment, 'model_dump') else {"visual": visual_text, "camera": "静态", "visual_fx": "无"}
                            prompt = build_master_prompt(seg_data)
                            if video_gen.generate(prompt, gen_path, duration=max(4, int(segment.duration))):
                                # Render with generated video + subtitles
                                ai_cmd = build_video_command(
                                    ffmpeg_path=self.settings.ffmpeg_path,
                                    input_path=gen_path,
                                    output_path=segment_path,
                                    ass_path=ass_path,
                                    duration=segment.duration,
                                    width=width, height=height,
                                    version=version, segment_type=segment.type,
                                    has_audio=False,
                                )
                                _run(ai_cmd)
                                if segment_path.exists() and segment_path.stat().st_size > 0:
                                    shot_used = True
                                    warnings.append(f"AI video generated for segment {segment.id}")

                    if not shot_used and is_reference and segment.source != "reorder":
                        # Do NOT use reference video for non-reorder segments —
                        # it shows the wrong product. Generate a clean packaging
                        # card with the correct product text instead.
                        render_card_path = work_dir / f"segment_{index:03d}_refcard.png"
                        render_packaging_card(
                            render_card_path,
                            title=_get_card_title(segment),
                            body=_strip_production_params(segment.script)[:60],
                            card_type=segment.type,
                            font_path=self.settings.packaging_font_path,
                        )
                        warnings.append(f"no matching shot for segment {segment.id}, used packaging card")
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
                        start_seconds = (
                            segment.source_start if is_reference and segment.source_start is not None
                            else segment.start if is_reference
                            else 0.0
                        )
                        # Mute audio for reference clips (new script ≠ original speech).
                        keep_audio = not is_reference and _has_audio_stream(source_path, self.settings.ffprobe_path)
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
                            has_audio=keep_audio,
                            start_seconds=start_seconds,
                        )
                _run(command)
                segment_files.append(segment_path)

            # ── TTS: generate AI voiceover for segments without original audio ──
            self.repository.update_render_job(job_id, progress=75, warnings=warnings)
            tts = TTSEngine(
                endpoint=self.settings.tts_endpoint or None,
                api_key=self.settings.tts_api_key,
                voice=self.settings.tts_voice,
                speed=self.settings.tts_speed,
            )
            if tts.available:
                # Clean script text before TTS — strip production params
                full_script = " ".join(_strip_production_params(s.script or "") for s in segments)
                if full_script.strip():
                    full_tts_path = work_dir / "full_script_tts.mp3"
                    total_dur = sum(max(s.duration, 0.5) for s in segments)
                    if tts.synthesize(full_script, full_tts_path, target_duration=total_dur):
                        # Split TTS audio proportionally to each segment's duration.
                        cursor = 0.0
                        for idx, segment in enumerate(segments):
                            seg_path = segment_files[idx]
                            seg_dur = max(segment.duration, 0.5)
                            tts_seg_path = work_dir / f"segment_{idx:03d}_tts.mp3"
                            _run([
                                self.settings.ffmpeg_path, "-y",
                                "-ss", f"{cursor:.3f}",
                                "-i", str(full_tts_path),
                                "-t", f"{seg_dur:.3f}",
                                "-c:a", "libmp3lame", str(tts_seg_path),
                            ])
                            cursor += seg_dur
                            if tts_seg_path.exists() and tts_seg_path.stat().st_size > 0:
                                mixed_path = work_dir / f"segment_{idx:03d}_mixed.mp4"
                                cmd = [
                                    self.settings.ffmpeg_path, "-y",
                                    "-i", str(seg_path),
                                    "-i", str(tts_seg_path),
                                    "-filter_complex", "[1:a]volume=0.9[tts];[0:a][tts]amix=inputs=2:duration=first",
                                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(mixed_path),
                                ]
                                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                                if result.returncode == 0 and mixed_path.exists() and mixed_path.stat().st_size > 0:
                                    mixed_path.replace(seg_path)
                                    segment_files[idx] = seg_path
                        warnings.append("TTS voiceover added to all segments (coherent)")
                    else:
                        warnings.append("TTS 语音合成失败，视频仅有背景音乐")
            else:
                warnings.append("TTS 未配置，请在 .env 中设置 STRUCTFORGE_TTS_API_KEY 以启用 AI 配音")

            # ── Phase 7: Animated overlays for CTA/Hook segments ──
            # Uses the Renderer Abstraction Layer: auto-selects Remotion or Pillow.
            render_engine = getattr(self, '_render_engine', None)
            if render_engine is None:
                remotion_url = self.settings.remotion_service_url if hasattr(self.settings, 'remotion_service_url') else None
                render_engine = RendererFactory.create(
                    remotion_url=remotion_url,
                    ffmpeg_path=self.settings.ffmpeg_path,
                    engine="auto",
                )
                self._render_engine = render_engine  # type: ignore[attr-defined]
                warnings.append(f"动画引擎: {render_engine.name}")

            for idx, segment in enumerate(segments):
                if segment.type in ("cta", "hook") and segment.script:
                    clean_script = _strip_production_params(segment.script)
                    overlay_path, fallback_reason = render_engine.render_for_segment(
                        segment_type=segment.type,
                        script_text=clean_script,
                        output_dir=work_dir,
                        duration=min(segment.duration, 2.5),
                    )
                    if fallback_reason:
                        warnings.append(fallback_reason)
                    if overlay_path:
                        seg_in = segment_files[idx]
                        mixed = work_dir / f"segment_{idx:03d}_animated.mp4"
                        cmd = [
                            self.settings.ffmpeg_path, "-y",
                            "-i", str(seg_in),
                            "-i", overlay_path,
                            "-filter_complex", "[0][1]overlay=0:0:format=auto",
                            "-c:v", "libx264", "-c:a", "aac",
                            "-pix_fmt", "yuv420p", str(mixed),
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                        if res.returncode == 0 and mixed.exists() and mixed.stat().st_size > 0:
                            mixed.replace(seg_in)
                            segment_files[idx] = seg_in
                            warnings.append(f"animated overlay for {segment.type}")

            self.repository.update_render_job(job_id, progress=80, warnings=warnings)
            output_path = output_dir / f"{version}.mp4"

            # Concat all segments using the concat filter (most reliable method).
            concat_output = output_path
            if len(segment_files) > 1:
                # Build concat filter: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[v][a]
                concat_parts = []
                concat_inputs = []
                for idx, sp in enumerate(segment_files):
                    concat_inputs.extend(["-i", str(sp)])
                    concat_parts.append(f"[{idx}:v][{idx}:a]")
                filter_complex = "".join(concat_parts) + f"concat=n={len(segment_files)}:v=1:a=1[v][a]"
                _run([
                    self.settings.ffmpeg_path, "-y",
                    *concat_inputs,
                    "-filter_complex", filter_complex,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(concat_output),
                ])
            elif len(segment_files) == 1:
                # Single segment: re-encode to ensure clean output
                _run([
                    self.settings.ffmpeg_path, "-y",
                    "-i", str(segment_files[0]),
                    "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(output_path),
                ])
            else:
                concat_output = output_path

            # Apply BGM mixing if a BGM directory is configured and has tracks.
            self.repository.update_render_job(job_id, progress=90, warnings=warnings)
            bgm = BGMEngine(
                bgm_dir=self.settings.bgm_library_dir if hasattr(self.settings, 'bgm_library_dir') else None,
                ffmpeg_path=self.settings.ffmpeg_path,
            )
            tracks = bgm.list_tracks()
            if not tracks:
                # Generate ambient BGM on-the-fly.
                ambient_path = work_dir / "ambient_bgm.mp3"
                generated = bgm.generate_ambient(ambient_path, duration=script.total_duration + 3)
                if generated:
                    tracks = [{"id": "ambient", "name": "Ambient", "path": generated, "duration": script.total_duration, "category": "minimal"}]
                    warnings.append("Auto-generated ambient BGM")

            if tracks:
                bgm_track = tracks[0]
                bgm_output = work_dir / f"{version}_bgm.mp4"
                try:
                    cmd = bgm.mix_command(
                        input_video=concat_output,
                        bgm_path=bgm_track["path"],
                        output_video=bgm_output,
                        volume=getattr(self.settings, 'bgm_volume', 0.08),
                    )
                    _run(cmd)
                    if bgm_output.exists() and bgm_output.stat().st_size > 0:
                        concat_output = bgm_output
                        output_path = output_dir / f"{version}.mp4"
                        concat_output.rename(output_path)
                    warnings.append(f"BGM mixed: {bgm_track['name']}")
                except Exception:
                    warnings.append("BGM mixing failed, using unmixed audio")

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


def _cinematic_motion(segment_type: str, width: int, height: int, duration: float) -> str:
    """Generate per-segment-type zoompan animation patterns.

    - hook: fast zoom-in with center focus (creates urgency)
    - pain: slow pan right-to-left (context reveal)
    - product: smooth zoom-in with slight upward drift (hero shot)
    - proof: slow horizontal scan with pause (detail inspection)
    - cta: aggressive zoom + upward push (conversion urgency)
    """
    d = max(duration, 1.0)
    base = f"d=1:s={width}x{height}:fps=30"

    if segment_type == "hook":
        # Fast zoom-in from 1.02x to 1.08x, centered
        return f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "pain":
        # Slow pan right-to-left, slight zoom-out (revealing context)
        return f"zoompan=z='max(zoom-0.0002,0.95)':x='iw/2-(iw/zoom/2)+2*on':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "product":
        # Smooth zoom-in with slight upward drift (hero shot)
        return f"zoompan=z='min(zoom+0.0005,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-1.5*on':{base}"
    elif segment_type == "proof":
        # Slow horizontal scan, slight zoom for detail
        return f"zoompan=z='min(zoom+0.0003,1.04)':x='iw/2-(iw/zoom/2)+3*sin(on*0.3)':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "cta":
        # Aggressive zoom + upward push (urgency)
        return f"zoompan=z='min(zoom+0.001,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-3*on':{base}"
    else:
        # Default: subtle Ken Burns zoom-in
        return f"zoompan=z='min(zoom+0.0004,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"


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
    # Segment-type-aware cinematic motion.
    zoom_filter = _cinematic_motion(segment_type, width, height, duration)
    animated_filters = f"{zoom_filter},{filters}"
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
        animated_filters,
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
    start_seconds: float = 0.0,
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type)
    command = [
        ffmpeg_path,
        "-y",
    ]
    if start_seconds > 0:
        command.extend(["-ss", f"{start_seconds:.3f}"])
    command.extend(["-i", str(input_path)])
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
        filters.extend(
            [
                "setpts=0.77*PTS",
                f"zoompan=z='min(zoom+0.0015,1.08)':d=1:s={width}x{height}:fps=30",
                "eq=contrast=1.12",
            ]
        )
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
    # Strip production parameters 【镜】【字】【速】【情】【视】 from subtitle text
    clean_script = _strip_production_params(segment.script or "")
    text = _ass_text(clean_script)
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


def _get_card_title(segment: Any) -> str:
    """Human-readable card title for each segment type."""
    type_titles = {
        "hook": "开场吸引",
        "pain": "用户痛点",
        "product": "产品展示",
        "proof": "信任背书",
        "cta": "立即行动",
        "demo": "效果演示",
        "offer": "限时优惠",
        "compare": "对比优势",
    }
    return type_titles.get(segment.type if hasattr(segment, 'type') else str(segment.type), segment.type.upper() if hasattr(segment, 'type') else "内容")


def _strip_production_params(script: str) -> str:
    """Remove 【镜】【字】【速】【情】【视】 production params from subtitle display text.

    "家人们直接炸了！【镜】快推【字】弹入【速】快【情】惊讶【视】震屏"
    → "家人们直接炸了！"
    """
    import re
    # Match the first occurrence of any 5-param pattern and strip from there
    # Pattern: 【镜|字|速|情|视】 followed by 1-8 Chinese/ASCII/paren chars
    cleaned = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', script)
    # Also handle any leftover standalone 【】 markers
    cleaned = re.sub(r'【[镜字速情视]】', '', cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or script


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


def _build_xfade_command(
    ffmpeg_path: str,
    segment_files: list[Path],
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    fade_duration: float = 0.3,
) -> list[str]:
    """Build FFmpeg command with xfade dissolve transitions between segments."""
    cmd: list[str] = [ffmpeg_path, "-y"]
    for f in segment_files:
        cmd.extend(["-i", str(f)])

    # Build filter complex for xfade transitions.
    filter_parts: list[str] = []
    prev_label = "[0:v]"
    for i in range(1, len(segment_files)):
        next_label = f"[v{i}]"
        xfade = (
            f"{prev_label}[{i}:v]xfade=transition=fade:duration={fade_duration:.2f}:offset=0"
            f"{next_label.split('[')[0]}"
        )
        filter_parts.append(xfade)
        prev_label = next_label

    filter_str = ";".join(filter_parts)
    # Pad the last output to match resolution
    filter_str += f";{prev_label}scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[vout]"

    # Mix audio: take first track (dominant), fade others
    audio_parts = []
    for i in range(len(segment_files)):
        audio_parts.append(f"[{i}:a]")
    audio_filter = f"{''.join(audio_parts)}amix=inputs={len(segment_files)}:duration=first:dropout_transition=2[aout]"

    cmd.extend([
        "-filter_complex", f"{filter_str};{audio_filter}",
        "-map", "[vout]", "-map", "[aout]",
        "-r", "30",
        "-c:v", "libx264", "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ])
    return cmd


def _find_shot_for_segment(
    segment_type: str,
    target_duration: float,
    shot_pool: list[dict[str, Any]],
    source_video_path: str | None,
) -> dict[str, Any] | None:
    """Find the best matching shot from the pool for a segment type.

    Matches by: vision scene_type → vision tags → duration similarity.
    """
    if not shot_pool or not source_video_path:
        return None

    type_keywords = {
        "hook": ["冲突画面", "悬念", "hook", "特写", "反转"],
        "pain": ["痛点场景", "困境", "pain", "场景", "情绪"],
        "product": ["产品特写", "product", "展示", "功能", "开箱"],
        "proof": ["演示证明", "proof", "对比", "数据", "测试"],
        "cta": ["优惠购买", "cta", "价格", "Logo", "行动"],
    }
    keywords = type_keywords.get(segment_type, [])

    scored: list[tuple[float, dict[str, Any]]] = []
    for shot in shot_pool:
        tags = [str(t).strip() for t in shot.get("tags", [])]
        scene_type = str(shot.get("scene_type", ""))
        score = 0.0
        # Exact scene type match
        if scene_type == segment_type:
            score += 50
        # Tag keyword match
        tag_hits = sum(1 for k in keywords for t in tags if k.lower() in t.lower())
        score += tag_hits * 15
        # Duration similarity (prefer shots close to target)
        shot_dur = float(shot.get("duration_s", shot.get("duration_ms", 3000) / 1000))
        dur_diff = abs(shot_dur - target_duration) / max(target_duration, 0.5)
        score += max(0, 20 - dur_diff * 20)
        if score > 0:
            scored.append((score, shot))

    if not scored:
        return None

    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    return {
        "source": source_video_path,
        "start_s": float(best.get("start_s", best.get("start_ms", 0) / 1000)),
        "duration_s": min(float(best.get("duration_s", best.get("duration_ms", 3000) / 1000)), target_duration),
    }


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
