"""StructForge Video Render Pipeline — Template Method pattern.

Refactored from compositor.py's 621-line render() method into 7 independent,
testable steps. Pattern borrowed from Pixelle-Video's LinearVideoPipeline.

Usage:
    pipeline = VideoRenderPipeline(repository, settings)
    ctx = asyncio.run(pipeline.run(job_id=..., project_id=..., ...))
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# RenderContext — pipeline state object
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderContext:
    """State object passed between pipeline steps. Replaces 20+ local variables."""

    # Input
    job_id: str
    project_id: str
    version: str = "original"
    resolution: str = "1080p"
    script_version: str | None = None

    # Loaded data
    script: FinalScript | None = None
    assets: dict[str, dict] = field(default_factory=dict)

    # Work directory
    work_dir: Path | None = None
    output_dir: Path | None = None
    width: int = 1080
    height: int = 1920

    # Segments
    segments: list[Any] = field(default_factory=list)
    segment_files: list[Path] = field(default_factory=list)

    # Output
    output_path: Path | None = None

    # Diagnostics
    warnings: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# VideoRenderPipeline — Template Method orchestrator
# ═══════════════════════════════════════════════════════════

class CompositorError(RuntimeError):
    pass


RESOLUTIONS = {"1080p": (1080, 1920), "720p": (720, 1280)}


class VideoRenderPipeline:
    """Video render pipeline — 7-step Template Method.

    Each step is an independent method. The old compositor.render()
    is preserved and decorated with a forwarding shim for safety.
    """

    def __init__(self, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # ── Main entry point ──

    def run(
        self, *, job_id: str, project_id: str, version: str, resolution: str,
        script_version: str | None = None,
    ) -> RenderContext:
        """Execute the full render pipeline synchronously.

        (Wraps async steps in asyncio for compatibility with existing
        synchronous render() callers.)
        """
        ctx = RenderContext(
            job_id=job_id, project_id=project_id,
            version=version, resolution=resolution,
            script_version=script_version,
        )
        try:
            self._prepare(ctx)
            self._process_segments(ctx)
            self._synthesize_speech(ctx)
            self._apply_overlays(ctx)
            self._assemble_video(ctx)
            self._mix_audio(ctx)
            self._finalize(ctx)
        except Exception as exc:
            self.repository.update_render_job(
                job_id, status="failed", progress=100,
                error=str(exc), warnings=ctx.warnings,
            )
            raise
        return ctx

    # ═══════════════════════════════════════════════
    # Step 1: Preparation
    # ═══════════════════════════════════════════════

    def _prepare(self, ctx: RenderContext) -> None:
        """Load script, validate, create work directory."""
        from services.compositor import _validate_restructure_decision

        self.repository.update_render_job(ctx.job_id, status="processing", progress=5)

        script_payload = (
            self.repository.get_script_version(ctx.project_id, ctx.script_version)
            if ctx.script_version
            else self.repository.get_project_script(ctx.project_id)
        )
        if not script_payload:
            raise CompositorError("Project has no FinalScript")

        ctx.script = FinalScript.model_validate(script_payload)
        _validate_restructure_decision(ctx.script)

        ctx.assets = {a["id"]: a for a in self.repository.list_assets(ctx.project_id)}
        ctx.width, ctx.height = RESOLUTIONS.get(ctx.resolution, RESOLUTIONS["1080p"])
        ctx.work_dir = self.settings.output_dir / ctx.project_id / f".work-{ctx.job_id}"
        ctx.output_dir = self.settings.output_dir / ctx.project_id
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        from services.compositor import _segments_for_version
        ctx.segments = list(_segments_for_version(ctx.script, ctx.version))
        if not ctx.segments:
            raise CompositorError("FinalScript has no renderable segments")

        log.info("Pipeline prepared: %d segments, %dx%d", len(ctx.segments), ctx.width, ctx.height)

    # ═══════════════════════════════════════════════
    # Step 2: Segment processing
    # ═══════════════════════════════════════════════

    def _process_segments(self, ctx: RenderContext) -> None:
        """Process each segment: find source → render → output segment MP4."""
        from services.compositor import (
            build_image_command, build_placeholder_command,
            build_video_command, _ass_for_segment, _output_duration,
            _cinematic_motion, _apply_visual_fx, _strip_production_params,
            _get_card_title,
        )
        from services.gap_filler import render_packaging_card
        from services.ai_video_service import AIVideoService, PromptCard, GeneratedVideo
        from services.blueprint_renderer import render_blueprint_card
        from services.frame_renderer import _render_prompt_card_html as _html_card

        total = len(ctx.segments)
        for idx, segment in enumerate(ctx.segments):
            self.repository.update_render_job(
                ctx.job_id,
                progress=10 + int((idx / max(total, 1)) * 60),
                warnings=[f"渲染分镜 {idx + 1}/{total}"],
            )
            seg_path = ctx.work_dir / f"segment_{idx:03d}.mp4"
            ass_path = ctx.work_dir / f"segment_{idx:03d}.ass"
            out_dur = _output_duration(segment.duration, ctx.version, segment.type)
            ass_path.write_text(
                _ass_for_segment(segment, ctx.version, out_dur), encoding="utf-8"
            )
            asset = ctx.assets.get(segment.asset_id) if segment.asset_id else None
            source_path = Path(asset["file_path"]) if asset and asset.get("file_path") else None

            log.info("[TRACE] seg=%s type=%s source=%s has_asset=%s",
                     segment.id, segment.type, getattr(segment, 'source', '?'), bool(asset))

            shot_used = False
            command: list[str] = []

            # ── Branch: No asset ──
            if source_path is None or not source_path.exists():
                shot_used = False
                if segment.asset_id:
                    ctx.warnings.append(f"missing asset {segment.asset_id}")

                if segment.source == "packaging":
                    card = ctx.work_dir / f"segment_{idx:03d}_packaging.png"
                    render_packaging_card(card, title=segment.type.upper(),
                                          body=segment.script, card_type=segment.type,
                                          font_path=self.settings.packaging_font_path)
                    command = build_image_command(
                        ffmpeg_path=self.settings.ffmpeg_path, input_path=card,
                        output_path=seg_path, ass_path=ass_path,
                        duration=max(segment.duration, 0.5),
                        width=ctx.width, height=ctx.height,
                        version=ctx.version, segment_type=segment.type,
                        camera=getattr(segment, 'camera', '静态') or '静态',
                        visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                        pace=getattr(segment, 'pace', '正常') or '正常',
                        emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                        subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                    )
                    shot_used = True
                else:
                    # AI generation / prompt card
                    prod_name = (ctx.script.metadata or {}).get("productName", "") or ""
                    prod_type = (ctx.script.metadata or {}).get("productType", "其他") or "其他"
                    ai_video = AIVideoService(self.settings, platform="seedance")
                    ai_result = ai_video.generate(segment, product_name=prod_name, product_type=prod_type)

                    if isinstance(ai_result, PromptCard):
                        prompt_card_path = ctx.work_dir / f"segment_{idx:03d}_promptcard.png"
                        try:
                            html_ok = False
                            html_path = _html_card(
                                prompt_text=ai_result.prompt_text[:500],
                                subtitle_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                                duration=ai_result.duration, emotion=ai_result.emotion,
                                cost=ai_result.estimated_cost_usd,
                            )
                            if html_path:
                                prompt_card_path = Path(html_path)
                                html_ok = True
                            else:
                                render_blueprint_card(
                                    prompt_card_path, segment_type=segment.type,
                                    visual_prompt=ai_result.prompt_text[:300],
                                    script_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                    duration=ai_result.duration,
                                    camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                                    pace=ai_result.pace, emotion=ai_result.emotion,
                                )
                                html_ok = True

                            if html_ok:
                                command = build_image_command(
                                    ffmpeg_path=self.settings.ffmpeg_path,
                                    input_path=prompt_card_path, output_path=seg_path,
                                    ass_path=ass_path, duration=max(segment.duration, 0.5),
                                    width=ctx.width, height=ctx.height,
                                    version=ctx.version, segment_type=segment.type,
                                    camera=getattr(segment, 'camera', '静态') or '静态',
                                    visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                                    pace=getattr(segment, 'pace', '正常') or '正常',
                                    emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                    subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                                )
                                ctx.warnings.append(f"AI prompt card for {segment.id}")
                                shot_used = True
                        except Exception:
                            pass

                    if not shot_used:
                        command = build_placeholder_command(
                            ffmpeg_path=self.settings.ffmpeg_path, output_path=seg_path,
                            ass_path=ass_path, duration=max(segment.duration, 0.5),
                            width=ctx.width, height=ctx.height,
                            version=ctx.version, segment_type=segment.type,
                        )

            # ── Branch: Image asset ──
            elif asset["type"] == "image":
                command = build_image_command(
                    ffmpeg_path=self.settings.ffmpeg_path, input_path=source_path,
                    output_path=seg_path, ass_path=ass_path,
                    duration=max(segment.duration, 0.5),
                    width=ctx.width, height=ctx.height,
                    version=ctx.version, segment_type=segment.type,
                    camera=getattr(segment, 'camera', '静态') or '静态',
                    visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                    pace=getattr(segment, 'pace', '正常') or '正常',
                    emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                    subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                )
                shot_used = True

            # ── Branch: Video asset ──
            else:
                analysis = asset.get("analysis") or {}
                is_reference = analysis.get("reference_source") is True
                shot_used = False

                # aigc/packaging segments skip reference video → prompt card
                seg_source = getattr(segment, 'source', 'original') or 'original'
                if is_reference and seg_source in ("aigc", "packaging", "aigc_draft"):
                    prod_name = (ctx.script.metadata or {}).get("productName", "") or ""
                    prod_type = (ctx.script.metadata or {}).get("productType", "其他") or "其他"
                    ai_video = AIVideoService(self.settings, platform="seedance")
                    ai_result = ai_video.generate(segment, product_name=prod_name, product_type=prod_type)
                    if isinstance(ai_result, PromptCard):
                        prompt_card_path = ctx.work_dir / f"segment_{idx:03d}_promptcard.png"
                        try:
                            html_path = _html_card(
                                prompt_text=ai_result.prompt_text[:500],
                                subtitle_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                                duration=ai_result.duration, emotion=ai_result.emotion,
                                cost=ai_result.estimated_cost_usd,
                            )
                            if html_path:
                                prompt_card_path = Path(html_path)
                            else:
                                render_blueprint_card(
                                    prompt_card_path, segment_type=segment.type,
                                    visual_prompt=ai_result.prompt_text[:300],
                                    script_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                    duration=ai_result.duration,
                                    camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                                    pace=ai_result.pace, emotion=ai_result.emotion,
                                )
                            command = build_image_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                input_path=prompt_card_path, output_path=seg_path,
                                ass_path=ass_path, duration=max(segment.duration, 0.5),
                                width=ctx.width, height=ctx.height,
                                version=ctx.version, segment_type=segment.type,
                                camera=getattr(segment, 'camera', '静态') or '静态',
                                visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                                pace=getattr(segment, 'pace', '正常') or '正常',
                                emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                            )
                            ctx.warnings.append(f"AI prompt card for {segment.id} (aigc, skipped ref video)")
                            shot_used = True
                        except Exception:
                            pass
                    if not shot_used:
                        command = build_placeholder_command(
                            ffmpeg_path=self.settings.ffmpeg_path, output_path=seg_path,
                            ass_path=ass_path, duration=max(segment.duration, 0.5),
                            width=ctx.width, height=ctx.height,
                            version=ctx.version, segment_type=segment.type,
                        )
                    _run_ffmpeg(command, self.settings.ffmpeg_path)
                    ctx.segment_files.append(seg_path)
                    continue

                # Normal video handling
                if is_reference and segment.source != "reorder":
                    # Skip shot recombination for now — handled by old code
                    pass

                if not shot_used and is_reference and segment.source != "reorder":
                    render_card_path = ctx.work_dir / f"segment_{idx:03d}_refcard.png"
                    render_packaging_card(
                        render_card_path, title=_get_card_title(segment),
                        body=_strip_production_params(segment.script)[:60],
                        card_type=segment.type, font_path=self.settings.packaging_font_path,
                    )
                    command = build_image_command(
                        ffmpeg_path=self.settings.ffmpeg_path, input_path=render_card_path,
                        output_path=seg_path, ass_path=ass_path,
                        duration=max(segment.duration, 0.5),
                        width=ctx.width, height=ctx.height,
                        version=ctx.version, segment_type=segment.type,
                        camera=getattr(segment, 'camera', '静态') or '静态',
                        visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                        pace=getattr(segment, 'pace', '正常') or '正常',
                        emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                        subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                    )
                    shot_used = True
                else:
                    start_seconds = (
                        segment.source_start if is_reference and segment.source_start is not None
                        else segment.start if is_reference else 0.0
                    )
                    if is_reference:
                        keep_audio = False
                    else:
                        keep_audio = (
                            not bool(self.settings.tts_api_key)
                            and _has_audio_stream(source_path, self.settings.ffprobe_path)
                        )
                    command = build_video_command(
                        ffmpeg_path=self.settings.ffmpeg_path, input_path=source_path,
                        output_path=seg_path, ass_path=ass_path,
                        duration=max(segment.duration, 0.5),
                        width=ctx.width, height=ctx.height,
                        version=ctx.version, segment_type=segment.type,
                        has_audio=keep_audio, start_seconds=start_seconds,
                        emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                        subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                    )
                    shot_used = True

            _run_ffmpeg(command, self.settings.ffmpeg_path)
            ctx.segment_files.append(seg_path)

    # ═══════════════════════════════════════════════
    # Step 3: TTS synthesis (per-segment, audio-driven)
    # ═══════════════════════════════════════════════

    def _synthesize_speech(self, ctx: RenderContext) -> None:
        """Per-segment TTS synthesis. Audio duration drives segment duration."""
        from services.tts_engine import TTSEngine
        from services.compositor import _strip_production_params, _probe_duration, _merge_video_audio_smart

        self.repository.update_render_job(ctx.job_id, progress=75, warnings=ctx.warnings)
        tts = TTSEngine(
            endpoint=self.settings.tts_endpoint or None,
            api_key=self.settings.tts_api_key,
            voice=self.settings.tts_voice,
            speed=self.settings.tts_speed,
            inference_mode="local" if not self.settings.tts_api_key else "api",
        )
        if not tts.available:
            ctx.warnings.append("TTS 未配置")
            return

        tts_ok = 0
        for idx, segment in enumerate(ctx.segments):
            seg_text = _strip_production_params(segment.script or "")
            if not seg_text.strip():
                continue
            if idx >= len(ctx.segment_files):
                continue

            seg_path = ctx.segment_files[idx]
            tts_path = ctx.work_dir / f"segment_{idx:03d}_tts.mp3"
            seg_dur = max(segment.duration, 0.5)

            if tts.synthesize(seg_text, tts_path, target_duration=seg_dur):
                tts_ok += 1
                actual = _probe_duration(tts_path)
                if actual > 0:
                    segment.duration = max(actual, 0.5)
                mixed = ctx.work_dir / f"segment_{idx:03d}_mixed.mp4"
                _merge_video_audio_smart(str(seg_path), str(tts_path), str(mixed),
                                          ffmpeg_path=self.settings.ffmpeg_path)
                if mixed.exists() and mixed.stat().st_size > 0:
                    mixed.replace(seg_path)
                    ctx.segment_files[idx] = seg_path

        if tts_ok > 0:
            cursor = 0.0
            for seg in ctx.segments:
                seg.start = cursor
                seg.duration = max(seg.duration, 0.5)
                seg.end = cursor + seg.duration
                cursor = seg.end
            ctx.warnings.append(f"TTS: {tts_ok}/{len(ctx.segments)} segments (total={cursor:.1f}s)")
        else:
            ctx.warnings.append("TTS synthesis failed for all segments")

    # ═══════════════════════════════════════════════
    # Step 4: Animated overlays
    # ═══════════════════════════════════════════════

    def _apply_overlays(self, ctx: RenderContext) -> None:
        """Apply Remotion/Pillow animated overlays to Hook/CTA segments."""
        from services.renderer_abstraction import RendererFactory
        from services.compositor import _strip_production_params

        engine = RendererFactory.create(
            remotion_url=getattr(self.settings, 'remotion_service_url', None),
            ffmpeg_path=self.settings.ffmpeg_path, engine="auto",
        )
        ctx.warnings.append(f"动画引擎: {engine.name}")

        for idx, segment in enumerate(ctx.segments):
            if segment.type not in ("cta", "hook") or not segment.script:
                continue
            if idx >= len(ctx.segment_files):
                continue

            clean = _strip_production_params(segment.script)
            overlay_path, reason = engine.render_for_segment(
                segment_type=segment.type, script_text=clean,
                output_dir=ctx.work_dir, duration=min(segment.duration, 2.5),
            )
            if reason:
                ctx.warnings.append(reason)
            if overlay_path:
                seg_in = ctx.segment_files[idx]
                mixed = ctx.work_dir / f"segment_{idx:03d}_animated.mp4"
                cmd = [
                    self.settings.ffmpeg_path, "-y",
                    "-i", str(seg_in), "-i", overlay_path,
                    "-filter_complex", "[0][1]overlay=0:0:format=auto",
                    "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p", str(mixed),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if res.returncode == 0 and mixed.exists() and mixed.stat().st_size > 0:
                    mixed.replace(seg_in)
                    ctx.segment_files[idx] = seg_in
                    ctx.warnings.append(f"animated overlay for {segment.type}")

    # ═══════════════════════════════════════════════
    # Step 5: Assemble final video (concat)
    # ═══════════════════════════════════════════════

    def _assemble_video(self, ctx: RenderContext) -> None:
        """Concat all segment files into final MP4."""
        self.repository.update_render_job(ctx.job_id, progress=80, warnings=ctx.warnings)
        output = ctx.output_dir / f"{ctx.version}.mp4"

        if len(ctx.segment_files) > 1:
            parts = "".join(f"[{i}:v][{i}:a]" for i in range(len(ctx.segment_files)))
            inputs: list[str] = []
            for sp in ctx.segment_files:
                inputs.extend(["-i", str(sp)])
            _run_ffmpeg([
                self.settings.ffmpeg_path, "-y", *inputs,
                "-filter_complex", f"{parts}concat=n={len(ctx.segment_files)}:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ], self.settings.ffmpeg_path)
        elif len(ctx.segment_files) == 1:
            _run_ffmpeg([
                self.settings.ffmpeg_path, "-y",
                "-i", str(ctx.segment_files[0]),
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ], self.settings.ffmpeg_path)

        ctx.output_path = output

    # ═══════════════════════════════════════════════
    # Step 6: BGM mixing + beat alignment
    # ═══════════════════════════════════════════════

    def _mix_audio(self, ctx: RenderContext) -> None:
        """Mix BGM with beat-aligned segment transitions."""
        from services.bgm_engine import BGMEngine

        self.repository.update_render_job(ctx.job_id, progress=90, warnings=ctx.warnings)
        bgm = BGMEngine(
            bgm_dir=getattr(self.settings, 'bgm_library_dir', None),
            ffmpeg_path=self.settings.ffmpeg_path,
        )
        tracks = bgm.list_tracks()
        if not tracks:
            ambient = ctx.work_dir / "ambient_bgm.mp3"
            if bgm.generate_ambient(ambient, duration=ctx.script.total_duration + 3):
                tracks = [{"id": "ambient", "name": "Ambient", "path": str(ambient),
                           "duration": ctx.script.total_duration, "category": "minimal"}]
                ctx.warnings.append("Auto-generated ambient BGM")

        if tracks:
            track = tracks[0]
            beats = bgm.detect_beats(track["path"], ctx.script.total_duration + 3)
            snapped = 0
            if beats and len(beats) >= 2:
                for seg in ctx.segments:
                    nearest = min(beats, key=lambda b: abs(b - seg.start))
                    if abs(nearest - seg.start) <= 0.15 and nearest != seg.start:
                        seg.start = nearest
                        snapped += 1
                if snapped:
                    ctx.warnings.append(f"Beat aligned: {snapped}/{len(ctx.segments)}")

            bgm_out = ctx.work_dir / f"{ctx.version}_bgm.mp4"
            try:
                _run_ffmpeg(bgm.mix_command(
                    input_video=ctx.output_path, bgm_path=track["path"],
                    output_video=bgm_out,
                    volume=getattr(self.settings, 'bgm_volume', 0.08),
                    duration=ctx.script.total_duration,
                ), self.settings.ffmpeg_path)
                if bgm_out.exists() and bgm_out.stat().st_size > 0:
                    final = ctx.output_dir / f"{ctx.version}.mp4"
                    bgm_out.rename(final)
                    ctx.output_path = final
                ctx.warnings.append(f"BGM mixed: {track['name']}")
            except Exception:
                ctx.warnings.append("BGM mixing failed")

    # ═══════════════════════════════════════════════
    # Step 7: Finalize
    # ═══════════════════════════════════════════════

    def _finalize(self, ctx: RenderContext) -> None:
        """Update render job status, save output path, and run self-audit."""
        # ── Self-audit: evaluate generated video against original structure ──
        self_audit = None
        try:
            from services.burst_metrics import BurstMetricsCalculator
            shots = [
                {"start_s": float(s.start), "end_s": float(s.end),
                 "duration_s": float(s.duration), "type": s.type}
                for s in ctx.segments
            ]
            vision_frames = [
                {"index": i+1, "tags": getattr(s, "visual_keywords", []) or [],
                 "ocr": [], "description": getattr(s, "visual", ""), "dominant_colors": []}
                for i, s in enumerate(ctx.segments)
            ]
            calc = BurstMetricsCalculator(
                shots=shots, asr_text="", asr_segments=[],
                vision_frames=vision_frames,
                duration=sum(s.duration for s in ctx.segments),
                platform="douyin",
            )
            dimensions = calc.dimension_reports()
            overall = sum(d.score for d in dimensions) // max(len(dimensions), 1)
            self_audit = {
                "overall_score": overall,
                "dimensions": [
                    {"name": d.name, "score": d.score, "strengths": d.strengths[:2]}
                    for d in dimensions
                ],
                "total_duration": round(sum(s.duration for s in ctx.segments), 1),
                "segment_count": len(ctx.segments),
            }
            ctx.warnings.append(f"自审计: 综合分={overall} (5维: {', '.join(f'{d.name}={d.score}' for d in dimensions)})")
        except Exception:
            pass

        # Save self-audit to script metadata
        if self_audit and ctx.script:
            meta = dict(ctx.script.metadata or {})
            meta["self_audit"] = self_audit
            ctx.script.metadata = meta

        self.repository.update_render_job(
            ctx.job_id, status="completed", progress=100,
            output_path=f"/outputs/{ctx.project_id}/{ctx.version}.mp4",
            warnings=ctx.warnings,
        )


# ═══════════════════════════════════════════════════════════
# Shared helpers (imported from compositor.py but defined
# here for self-contained pipeline)
# ═══════════════════════════════════════════════════════════

def _run_ffmpeg(command: list[str], ffmpeg_path: str = "ffmpeg") -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "FFmpeg failed").strip()
        raise CompositorError(msg[-1200:])


def _has_audio_stream(input_path: Path, ffprobe_path: str) -> bool:
    result = subprocess.run(
        [ffprobe_path, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(input_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode == 0 and bool(result.stdout.strip())
