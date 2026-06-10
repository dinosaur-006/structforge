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
    segment_modes: dict[str, str] | None = None  # {seg_id: "image"|"video"}

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

    # TTS paths (dict keyed by segment index — avoids Pydantic model attribute issues)
    tts_paths: dict[int, Path] = field(default_factory=dict)
    # Track actual visual source per segment (Flux vs Pillow vs Original)
    visual_sources: dict[int, str] = field(default_factory=dict)

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

    # ── Helper: generate visual via ComfyUI Flux ──

    def _generate_ai_visual(
        self, prompt_text: str, subtitle: str, segment: Any, idx: int, ctx: RenderContext,
        negative_prompt: str = "",
        force_video: bool = False,
    ) -> Path:
        """Generate AI visual.

        Strategy:
        - ComfyUI RunningHub configured → Flux real AI image (best quality)
        - ComfyUI NOT configured → Pillow blueprint card (single clear fallback)
        - Never silently degrades — every path is explicit.
        """
        from services.comfyui_service import create_comfyui_service
        comfyui = create_comfyui_service(self.settings)

        if comfyui.available:
            # ── Primary: ComfyUI Flux ──
            import asyncio as _asyncio
            import httpx as _httpx
            log.info("[ComfyUI] Generating Flux image for %s", segment.id)

            flux_result = None
            _loop = _asyncio.new_event_loop()
            try:
                _asyncio.set_event_loop(_loop)
                flux_result = _loop.run_until_complete(
                    comfyui.generate_image(
                        prompt=prompt_text[:500] if prompt_text else "product showcase",
                        width=ctx.width, height=ctx.height,
                        negative_prompt=negative_prompt or None,
                    )
                )
            except Exception as exc:
                log.warning("[ComfyUI] Generation failed for %s: %s — falling back to Pillow", segment.id, exc)
                ctx.warnings.append(f"ComfyUI排队已满，{segment.id} 使用Pillow备用渲染")
            finally:
                _loop.close()

            if flux_result and flux_result.get("url"):
                flux_path = ctx.work_dir / f"segment_{idx:03d}_flux.png"
                # ── Download with retry + auth headers (RunningHub CDN requires API key) ──
                api_key = getattr(self.settings, 'runninghub_api_key', None)
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                download_ok = False
                last_error = None
                for attempt in range(3):
                    try:
                        resp = _httpx.get(flux_result["url"], headers=headers, follow_redirects=True, timeout=30)
                        if resp.status_code == 200 and len(resp.content) > 100:
                            flux_path.write_bytes(resp.content)
                            download_ok = True
                            break
                        else:
                            last_error = f"HTTP {resp.status_code}, size={len(resp.content)}"
                    except Exception as exc:
                        last_error = exc
                    if attempt < 2:
                        import time as _time
                        _time.sleep(1.0 * (attempt + 1))
                if download_ok:
                    if force_video:
                        video_path = self._generate_ai_video(flux_path, prompt_text, segment, idx, ctx)
                        if video_path:
                            ctx.visual_sources[idx] = "wan2.2"
                            return video_path
                    preview_dir = ctx.output_dir / "flux_previews"
                    preview_dir.mkdir(parents=True, exist_ok=True)
                    import shutil as _shutil
                    preview_path = preview_dir / f"segment_{idx:03d}.png"
                    _shutil.copy2(str(flux_path), str(preview_path))
                    ctx.warnings.append(f"ComfyUI Flux: {segment.id}")
                    log.info("ComfyUI Flux OK: %s (%d bytes)", segment.id, flux_path.stat().st_size)
                    return flux_path
        # ── Fallback: Pillow blueprint ──
        log.info("[Blueprint] Rendering Pillow card for %s", segment.id)
        from services.blueprint_renderer import render_blueprint_card
        card_path = ctx.work_dir / f"segment_{idx:03d}_promptcard.png"
        render_blueprint_card(
            card_path, segment_type=getattr(segment, 'type', 'hook'),
            visual_prompt=prompt_text[:300],
            script_text=subtitle or '',
            duration=float(getattr(segment, 'duration', 3)),
            camera=getattr(segment, 'camera', '静态') or '静态',
            visual_fx=getattr(segment, 'visual_fx', '无') or '无',
            pace=getattr(segment, 'pace', '正常') or '正常',
            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
        )
        if not card_path.exists() or card_path.stat().st_size < 100:
            raise CompositorError(f"Pillow blueprint failed for {segment.id} (output missing or empty)")
        ctx.warnings.append(f"Prompt Card: {segment.id}")
        return card_path

    def _generate_ai_video(self, image_path: Path, prompt_text: str, segment: Any, idx: int, ctx: RenderContext) -> Path | None:
        """Generate WAN 2.2 video from a Flux image via RunningHub.

        Returns the video path on success, None if video generation is unavailable or failed.
        """
        from services.comfyui_service import create_comfyui_service
        comfyui = create_comfyui_service(self.settings)
        if not comfyui.available:
            return None

        import asyncio as _asyncio
        import httpx as _httpx
        video_path = ctx.work_dir / f"segment_{idx:03d}_wan.mp4"
        seg_dur = float(getattr(segment, 'duration', 3))
        log.info("[WAN] Generating video for %s (%.1fs)", segment.id, seg_dur)

        _loop = _asyncio.new_event_loop()
        try:
            _asyncio.set_event_loop(_loop)
            video_result = _loop.run_until_complete(
                comfyui.generate_video(
                    prompt=prompt_text[:300] if prompt_text else "product showcase video",
                    image_path=str(image_path),
                    width=ctx.width, height=ctx.height,
                    duration=min(seg_dur, 5.0),
                )
            )
        except Exception as exc:
            log.warning("[WAN] Video generation failed for %s: %s", segment.id, exc)
            return None
        finally:
            _loop.close()

        if not video_result.get("url"):
            return None

        # Download with auth
        api_key = getattr(self.settings, 'runninghub_api_key', None)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        for attempt in range(3):
            try:
                resp = _httpx.get(video_result["url"], headers=headers, follow_redirects=True, timeout=120)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    video_path.write_bytes(resp.content)
                    ctx.warnings.append(f"WAN 2.2 Video: {segment.id}")
                    log.info("WAN 2.2 Video OK: %s (%d bytes)", segment.id, video_path.stat().st_size)
                    return video_path
            except Exception as exc:
                if attempt < 2:
                    import time as _time
                    _time.sleep(2.0 * (attempt + 1))
        log.warning("[WAN] Video download failed for %s", segment.id)
        return None

    # ── Main entry point ──

    def run(
        self, *, job_id: str, project_id: str, version: str, resolution: str,
        script_version: str | None = None,
        segment_modes: dict[str, str] | None = None,
    ) -> RenderContext:
        """Execute the full render pipeline synchronously.

        (Wraps async steps in asyncio for compatibility with existing
        synchronous render() callers.)
        """
        ctx = RenderContext(
            job_id=job_id, project_id=project_id,
            version=version, resolution=resolution,
            script_version=script_version,
            segment_modes=segment_modes or {},
        )
        try:
            self._prepare(ctx)
            self._synthesize_all_tts(ctx)    # ← PIXELLE PATTERN: TTS BEFORE video!
            self._process_segments(ctx)       # Now uses audio-driven durations
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

    def _validate_config(self, ctx: RenderContext) -> list[str]:
        """Check essential configuration before rendering. Returns list of issues."""
        issues: list[str] = []
        if not self.settings.doubao_llm_endpoint or not self.settings.doubao_llm_api_key:
            issues.append("LLM 未配置 — 脚本生成和结构分析将不可用")
        if not self.settings.ffmpeg_path or self.settings.ffmpeg_path == "ffmpeg":
            import shutil as _shutil
            if not _shutil.which("ffmpeg"):
                issues.append("FFmpeg 未安装 — 视频合成将失败")
        # TTS is optional (Edge TTS is free and always available)
        # ComfyUI is optional (Prompt Card fallback available)
        return issues

    def _prepare(self, ctx: RenderContext) -> None:
        """Load script, validate, create work directory."""
        from services.compositor import _validate_restructure_decision

        # ── Config validation ──
        config_issues = self._validate_config(ctx)
        if config_issues:
            ctx.warnings.extend(config_issues)

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
        # Use original video's resolution for AI generation consistency
        project = self.repository.get_project(ctx.project_id)
        video_resolution = "1080x1920"
        if project:
            analysis = project.get("analysis_result") or {}
            video_resolution = str(analysis.get("meta", {}).get("resolution", "1080x1920"))
        try:
            w, h = video_resolution.split("x")
            ctx.width, ctx.height = int(w), int(h)
        except (ValueError, TypeError):
            ctx.width, ctx.height = RESOLUTIONS.get(ctx.resolution, (1080, 1920))
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
        from services.blueprint_renderer import render_blueprint_card
        from services.flux_prompt_generator import FluxPromptGenerator
        from services.prompt_engine.negative_prompts import select_negatives

        total = len(ctx.segments)
        for idx, segment in enumerate(ctx.segments):
            seg_mode = (ctx.segment_modes or {}).get(segment.id, "image")
            mode_label = "视频" if seg_mode == "video" else "图片"
            self.repository.update_render_job(
                ctx.job_id,
                progress=10 + int((idx / max(total, 1)) * 60),
                warnings=[f"生成: {segment.type} ({mode_label}) {idx+1}/{total}"],
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

                # ── ALL no-asset segments: LLM-generated Flux prompt → ComfyUI ──
                script_meta = ctx.script.metadata or {}
                prod_name = script_meta.get("productName", "") or ""
                prod_type = script_meta.get("productType", "其他") or "其他"
                product_visual = script_meta.get("productVisual") or {}

                prompt_gen = FluxPromptGenerator(self.settings)
                flux_prompt = prompt_gen.generate(
                    segment_type=segment.type,
                    script=segment.script or "",
                    visual=getattr(segment, 'visual', '') or "",
                    camera=getattr(segment, 'camera', '静态') or '静态',
                    emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                    duration=float(getattr(segment, 'duration', 3)),
                    product_name=prod_name,
                    product_type=prod_type,
                    product_vision_tags=product_visual.get("tags") if isinstance(product_visual, dict) else None,
                    product_vision_colors=product_visual.get("colors") if isinstance(product_visual, dict) else None,
                    width=ctx.width, height=ctx.height,
                )
                neg_prompt = select_negatives("flux", segment_type=segment.type, include_product=True)

                # Check if user wants video for this segment
                seg_mode = (ctx.segment_modes or {}).get(segment.id, "image")
                if seg_mode == "video":
                    ctx.warnings.append(f"Video mode: {segment.id}")

                visual_input = self._generate_ai_visual(
                    prompt_text=flux_prompt,
                    subtitle=_strip_production_params(segment.script or ""),
                    segment=segment, idx=idx, ctx=ctx,
                    negative_prompt=neg_prompt,
                    force_video=(seg_mode == "video"),
                )
                if visual_input and visual_input.exists() and visual_input.stat().st_size > 100:
                    is_video = visual_input.suffix in ('.mp4', '.webm', '.mov')
                    if is_video:
                        # WAN 2.2 video — normalize to consistent format for concat
                        import shutil as _shutil
                        temp_video = ctx.work_dir / f"segment_{idx:03d}_temp.mp4"
                        _shutil.copy2(str(visual_input), str(temp_video))
                        command = build_video_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=temp_video, output_path=seg_path,
                            ass_path=ass_path, duration=max(segment.duration, 0.5),
                            width=ctx.width, height=ctx.height,
                            version=ctx.version, segment_type=segment.type,
                            has_audio=False, start_seconds=0.0,
                            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                            subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                        )
                    else:
                        command = build_image_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=visual_input, output_path=seg_path,
                            ass_path=ass_path, duration=max(segment.duration, 0.5),
                            width=ctx.width, height=ctx.height,
                            version=ctx.version, segment_type=segment.type,
                            camera=getattr(segment, 'camera', '静态') or '静态',
                            visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                            pace=getattr(segment, 'pace', '正常') or '正常',
                            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                            subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                        )
                    shot_used = True
                    is_flux = 'flux' in str(visual_input).lower()
                    ctx.warnings.append(f"{'ComfyUI Flux' if is_flux else 'Prompt Card'}: {segment.id}")

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
                if is_reference and seg_source != "reorder":
                    script_meta2 = ctx.script.metadata or {}
                    prod_name = script_meta2.get("productName", "") or ""
                    prod_type = script_meta2.get("productType", "其他") or "其他"
                    product_visual2 = script_meta2.get("productVisual") or {}

                    prompt_gen2 = FluxPromptGenerator(self.settings)
                    flux_prompt = prompt_gen2.generate(
                        segment_type=segment.type,
                        script=segment.script or "",
                        visual=getattr(segment, 'visual', '') or "",
                        camera=getattr(segment, 'camera', '静态') or '静态',
                        emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                        duration=float(getattr(segment, 'duration', 3)),
                        product_name=prod_name,
                        product_type=prod_type,
                        product_vision_tags=product_visual2.get("tags") if isinstance(product_visual2, dict) else None,
                        product_vision_colors=product_visual2.get("colors") if isinstance(product_visual2, dict) else None,
                        width=ctx.width, height=ctx.height,
                    )
                    neg_prompt2 = select_negatives("flux", segment_type=segment.type, include_product=True)
                    seg_mode2 = (ctx.segment_modes or {}).get(segment.id, "image")

                    visual_input = self._generate_ai_visual(
                        prompt_text=flux_prompt,
                        subtitle=_strip_production_params(segment.script or ""),
                        negative_prompt=neg_prompt2,
                        segment=segment, idx=idx, ctx=ctx,
                        force_video=(seg_mode2 == "video"),
                    )
                    if visual_input and visual_input.exists():
                        is_video2 = visual_input.suffix in ('.mp4', '.webm', '.mov')
                        if is_video2:
                            import shutil as _shutil2
                            temp = ctx.work_dir / f"segment_{idx:03d}_temp2.mp4"
                            _shutil2.copy2(str(visual_input), str(temp))
                            command = build_video_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                input_path=temp, output_path=seg_path,
                                ass_path=ass_path, duration=max(segment.duration, 0.5),
                                width=ctx.width, height=ctx.height,
                                version=ctx.version, segment_type=segment.type,
                                has_audio=False, start_seconds=0.0,
                                emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                            )
                        else:
                            command = build_image_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                input_path=visual_input, output_path=seg_path,
                                ass_path=ass_path, duration=max(segment.duration, 0.5),
                                width=ctx.width, height=ctx.height,
                                version=ctx.version, segment_type=segment.type,
                                camera=getattr(segment, 'camera', '静态') or '静态',
                                visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                                pace=getattr(segment, 'pace', '正常') or '正常',
                                emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                            )
                        ctx.warnings.append(f"AI visual: {segment.id} (aigc, skipped ref video)")
                        shot_used = True
                    if not shot_used:
                        command = build_placeholder_command(
                            ffmpeg_path=self.settings.ffmpeg_path, output_path=seg_path,
                            ass_path=ass_path, duration=max(segment.duration, 0.5),
                            width=ctx.width, height=ctx.height,
                            version=ctx.version, segment_type=segment.type,
                        )
                    _run_ffmpeg(command, self.settings.ffmpeg_path)
                    ctx.segment_files.append(seg_path)
                    ctx.warnings.append(f"✓ {idx}:{segment.type}")
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

            # ── Merge pre-generated TTS audio (Pixelle-Video pattern) ──
            tts_path = ctx.tts_paths.get(idx)
            if tts_path and Path(str(tts_path)).exists():
                from services.compositor import _merge_video_audio_smart
                mixed = ctx.work_dir / f"segment_{idx:03d}_mixed.mp4"
                _merge_video_audio_smart(
                    str(seg_path), str(tts_path), str(mixed),
                    ffmpeg_path=self.settings.ffmpeg_path,
                )
                if mixed.exists() and mixed.stat().st_size > 0:
                    mixed.replace(seg_path)

            ctx.segment_files.append(seg_path)
            ctx.warnings.append(f"✓ {idx}:{segment.type}")

    # ═══════════════════════════════════════════════
    # Step 2: TTS synthesis (BEFORE video — Pixelle-Video pattern)
    # ═══════════════════════════════════════════════

    def _synthesize_all_tts(self, ctx: RenderContext) -> None:
        """Generate TTS for all segments FIRST. Audio duration drives segment duration.

        This is the key Pixelle-Video architectural decision:
        TTS audio determines how long each segment is, not the other way around.
        """
        from services.tts_engine import TTSEngine
        from services.compositor import _strip_production_params, _probe_duration

        self.repository.update_render_job(ctx.job_id, progress=10, warnings=ctx.warnings)
        tts = TTSEngine(
            endpoint=self.settings.tts_endpoint or None,
            api_key=self.settings.tts_api_key,
            voice=self.settings.tts_voice,
            speed=self.settings.tts_speed,
            inference_mode="local" if not self.settings.tts_api_key else "api",
        )
        if not tts.available:
            ctx.warnings.append("TTS 未配置 — 视频将仅有背景音乐")
            # Mark all segments as having no TTS
            for i in range(len(ctx.segments)):
                ctx.tts_paths[i] = None
            return

        tts_ok = 0
        total = len(ctx.segments)
        for idx, segment in enumerate(ctx.segments):
            # Push real-time TTS progress via render job warnings
            self.repository.update_render_job(
                ctx.job_id,
                warnings=[f"TTS 配音: {idx + 1}/{total} ({segment.type})"],
            )
            seg_text = _strip_production_params(segment.script or "")
            if not seg_text.strip():
                ctx.tts_paths[idx] = None
                continue

            tts_path = ctx.work_dir / f"segment_{idx:03d}_tts.mp3"
            seg_dur = max(segment.duration, 0.5)

            if tts.synthesize(seg_text, tts_path, target_duration=seg_dur):
                tts_ok += 1
                actual = _probe_duration(tts_path)
                if actual > 0:
                    # KEY: use actual TTS duration, not LLM-estimated duration
                    segment.duration = max(actual, 0.5)
                ctx.tts_paths[idx] = tts_path
            else:
                ctx.tts_paths[idx] = None

        # ── Reflow timeline based on actual audio durations ──
        if tts_ok > 0:
            cursor = 0.0
            for seg in ctx.segments:
                seg.start = cursor
                seg.duration = max(seg.duration, 0.5)
                seg.end = cursor + seg.duration
                cursor = seg.end
            ctx.warnings.append(
                f"TTS: {tts_ok}/{len(ctx.segments)} segments "
                f"(audio-driven duration, total={cursor:.1f}s)"
            )
        else:
            ctx.warnings.append("TTS synthesis failed for all segments — 视频仅有字幕")

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

        # Validate all segment files exist
        missing = [sp for sp in ctx.segment_files if not sp.exists() or sp.stat().st_size < 100]
        if missing:
            raise CompositorError(f"Missing segment files: {[m.name for m in missing]}")

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
        # ── Self-audit: record objective generation quality data ──
        self_audit = None
        try:
            # Count ComfyUI Flux vs fallback
            flux_count = 0
            fallback_count = 0
            for idx, s in enumerate(ctx.segments):
                flux_path = ctx.work_dir / f"segment_{idx:03d}_flux.png"
                if flux_path.exists():
                    flux_count += 1
                else:
                    fallback_count += 1

            visual_quality = "excellent" if flux_count >= len(ctx.segments) * 0.8 else \
                            "good" if flux_count >= len(ctx.segments) * 0.5 else \
                            "basic" if flux_count > 0 else "fallback"

            self_audit = {
                "total_duration": round(sum(s.duration for s in ctx.segments), 1),
                "segment_count": len(ctx.segments),
                "visual_generation": {
                    "method": "ComfyUI Flux" if flux_count > 0 else "Prompt Card",
                    "quality": visual_quality,
                    "flux_segments": flux_count,
                    "fallback_segments": fallback_count,
                    "per_segment": {str(k): v for k, v in ctx.visual_sources.items()},
                },
                "audio_generation": {
                    "method": "Edge TTS" if any((ctx.work_dir / f"segment_{i:03d}_tts.mp3").exists()
                                                 for i in range(len(ctx.segments))) else "None",
                },
            }
            ctx.warnings.append(
                f"渲染完成: {'ComfyUI Flux' if flux_count > 0 else 'Prompt Card'}"
                f" ({flux_count}/{len(ctx.segments)}段)"
            )
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
        # Extract the actual error (last non-empty lines, skip build config noise)
        lines = [l.strip() for l in (result.stderr + '\n' + result.stdout).split('\n') if l.strip()]
        error_lines = [l for l in lines[-10:] if 'error' in l.lower() or 'invalid' in l.lower() or 'no such file' in l.lower() or 'cannot' in l.lower()]
        if error_lines:
            msg = '; '.join(error_lines[-3:])
        else:
            msg = '; '.join(lines[-5:]) if lines else 'FFmpeg failed'
        raise CompositorError(f"FFmpeg error: {msg[:500]}")


def _has_audio_stream(input_path: Path, ffprobe_path: str) -> bool:
    result = subprocess.run(
        [ffprobe_path, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(input_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode == 0 and bool(result.stdout.strip())
