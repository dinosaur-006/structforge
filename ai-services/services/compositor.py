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
from services.ai_video_service import AIVideoService, PromptCard, GeneratedVideo
from services.bgm_engine import BGMEngine
from services.tts_engine import TTSEngine
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
        # ── Routing: use new pipeline if enabled ──
        use_new = getattr(self.settings, 'use_new_pipeline', True)
        if use_new:
            from services.render_pipeline import VideoRenderPipeline
            pipeline = VideoRenderPipeline(self.repository, self.settings)
            pipeline.run(job_id=job_id, project_id=project_id,
                         version=version, resolution=resolution,
                         script_version=script_version)
            return

        # ── Legacy render path (preserved for backward compatibility) ──
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

                # ── FORCE DIAGNOSTIC ──
                import sys as _sys
                _sys.stderr.write(
                    f"[COMPOSITOR-DIAG] seg={segment.id} type={segment.type} "
                    f"source={getattr(segment, 'source', '?')} "
                    f"asset_id={segment.asset_id} "
                    f"asset_found={bool(asset)} "
                    f"src_path_exists={source_path.exists() if source_path else 'NONE'}\n"
                )
                _sys.stderr.flush()

                # ── TRACE: log every segment's render plan ──
                log.info(
                    "[TRACE] seg=%s type=%s source=%s has_asset=%s asset_type=%s src_path=%s",
                    segment.id, segment.type, getattr(segment, 'source', '?'),
                    bool(asset), asset.get("type") if asset else "none",
                    source_path.name if source_path else "none",
                )
                if source_path is None or not source_path.exists():
                    shot_used = False  # needed for no-asset branches below
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
                            camera=getattr(segment, 'camera', '静态') or '静态',
                            visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                            pace=getattr(segment, 'pace', '正常') or '正常',
                            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                            subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                        )
                    else:
                        # ── aigc segment → ALWAYS render prompt card (Pixelle-Video pattern) ──
                        # No try/except, no shot_used flag — unconditional, just like Pixelle's
                        # _step_compose_frame which always runs regardless of media availability.
                        _sys.stderr.write(f"[COMPOSITOR] AIGC prompt card for {segment.id} (source={getattr(segment, 'source', '?')})\n")
                        _sys.stderr.flush()

                        prod_name = (script.metadata or {}).get("productName", "") or ""
                        prod_type = (script.metadata or {}).get("productType", "其他") or "其他"
                        ai_result = AIVideoService(self.settings).generate(segment, product_name=prod_name, product_type=prod_type)

                        # Step 1: generate the card image (Pillow — always works, no Playwright needed)
                        prompt_card_path = work_dir / f"segment_{index:03d}_promptcard.png"
                        from services.blueprint_renderer import render_blueprint_card
                        render_blueprint_card(
                            prompt_card_path,
                            segment_type=segment.type,
                            visual_prompt=(ai_result.prompt_text if isinstance(ai_result, PromptCard) else (getattr(segment, 'visual', '') or ''))[:300],
                            script_text=_strip_production_params(segment.script or ""),
                            duration=float(getattr(ai_result, 'duration', segment.duration)),
                            camera=getattr(ai_result, 'camera', '静态') if isinstance(ai_result, PromptCard) else '静态',
                            visual_fx=getattr(ai_result, 'visual_fx', '无') if isinstance(ai_result, PromptCard) else '无',
                            pace=getattr(ai_result, 'pace', '正常') if isinstance(ai_result, PromptCard) else '正常',
                            emotion=getattr(ai_result, 'emotion', '亲切') if isinstance(ai_result, PromptCard) else '亲切',
                        )
                        _sys.stderr.write(f"[COMPOSITOR] Card rendered: {prompt_card_path.stat().st_size} bytes\n")
                        _sys.stderr.flush()

                        # Step 2: convert card image to video segment (FFmpeg -loop 1)
                        command = build_image_command(
                            ffmpeg_path=self.settings.ffmpeg_path,
                            input_path=prompt_card_path,
                            output_path=segment_path,
                            ass_path=ass_path,
                            duration=max(segment.duration, 0.5),
                            width=width, height=height,
                            version=version, segment_type=segment.type,
                            camera=getattr(segment, 'camera', '静态') or '静态',
                            visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                            pace=getattr(segment, 'pace', '正常') or '正常',
                            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                            subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                        )
                        warnings.append(f"AI prompt card for {segment.id}")
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

                    # ── AI/Packaging segments must NOT use reference video ──
                    # These segments were marked for AI generation or packaging during
                    # migration. Even if reference_assets bound the reference video to them,
                    # we skip shot recombination and force the AI/prompt-card path.
                    seg_source = getattr(segment, 'source', 'original') or 'original'
                    if is_reference and seg_source in ("aigc", "packaging", "aigc_draft"):
                        # Treat this as a no-asset segment — go to AI generation
                        asset_id_saved = segment.asset_id
                        segment.asset_id = None
                        source_path = None
                        # Fall through to the source_path is None branch via the outer if
                        # Actually we need to inline the AI generation here
                        prod_name = (script.metadata or {}).get("productName", "") or ""
                        prod_type = (script.metadata or {}).get("productType", "其他") or "其他"
                        ai_video = AIVideoService(self.settings, platform="seedance")
                        ai_result = ai_video.generate(segment, product_name=prod_name, product_type=prod_type)
                        if isinstance(ai_result, PromptCard):
                            prompt_card_path = work_dir / f"segment_{index:03d}_promptcard.png"
                            try:
                                # Try HTML template (Playwright) first, then Pillow fallback
                                prompt_card_done = False
                                html_path = _render_prompt_card_html(
                                    prompt_text=ai_result.prompt_text[:500],
                                    subtitle_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                    camera=ai_result.camera,
                                    visual_fx=ai_result.visual_fx,
                                    duration=ai_result.duration,
                                    emotion=ai_result.emotion,
                                    cost=ai_result.estimated_cost_usd,
                                )
                                if html_path:
                                    prompt_card_path = Path(html_path)
                                    prompt_card_done = True
                                else:
                                    from services.blueprint_renderer import render_blueprint_card
                                    render_blueprint_card(
                                        prompt_card_path,
                                        segment_type=segment.type,
                                        visual_prompt=ai_result.prompt_text[:300],
                                        script_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                        duration=ai_result.duration,
                                        camera=ai_result.camera,
                                        visual_fx=ai_result.visual_fx,
                                        pace=ai_result.pace,
                                        emotion=ai_result.emotion,
                                    )
                                    prompt_card_done = True

                                if prompt_card_done:
                                    command = build_image_command(
                                    ffmpeg_path=self.settings.ffmpeg_path,
                                    input_path=prompt_card_path,
                                    output_path=segment_path,
                                    ass_path=ass_path,
                                    duration=max(segment.duration, 0.5),
                                    width=width, height=height,
                                    version=version, segment_type=segment.type,
                                    camera=getattr(segment, 'camera', '静态') or '静态',
                                    visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                                    pace=getattr(segment, 'pace', '正常') or '正常',
                                    emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                    subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                                )
                                warnings.append(f"AI prompt card for {segment.id} (aigc segment, skipped reference video)")
                                shot_used = True
                            except Exception:
                                pass
                        if not shot_used:
                            command = build_placeholder_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                output_path=segment_path,
                                ass_path=ass_path,
                                duration=max(segment.duration, 0.5),
                                width=width, height=height,
                                version=version, segment_type=segment.type,
                            )
                        # Restore asset_id
                        segment.asset_id = asset_id_saved
                        _run(command)
                        segment_files.append(segment_path)
                        continue  # skip the rest of the segment processing

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

                    # ── AI Video Generation via AIVideoService (decoupled from compositor) ──
                    if not shot_used and is_reference and segment.source != "reorder":
                        # Get product context from script metadata
                        prod_name = (script.metadata or {}).get("productName", "") or ""
                        prod_type = (script.metadata or {}).get("productType", "其他") or "其他"

                        ai_video = AIVideoService(self.settings, platform="seedance")
                        ai_result = ai_video.generate(
                            segment,
                            product_name=prod_name,
                            product_type=prod_type,
                        )

                        if isinstance(ai_result, GeneratedVideo):
                            # Real AI video generated successfully
                            ai_cmd = build_video_command(
                                ffmpeg_path=self.settings.ffmpeg_path,
                                input_path=ai_result.video_path,
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
                                warnings.append(f"AI video generated for segment {segment.id} ({ai_result.generation_time:.1f}s)")

                        elif isinstance(ai_result, PromptCard):
                            # ── Prompt Card: render the prompt as a visual card ──
                            prompt_card_path = work_dir / f"segment_{index:03d}_promptcard.png"
                            try:
                                from services.blueprint_renderer import render_blueprint_card
                                render_blueprint_card(
                                    prompt_card_path,
                                    segment_type=segment.type,
                                    visual_prompt=ai_result.prompt_text[:300],
                                    script_text=ai_result.subtitle_text or _strip_production_params(segment.script or ""),
                                    duration=ai_result.duration,
                                    camera=ai_result.camera,
                                    visual_fx=ai_result.visual_fx,
                                    pace=ai_result.pace,
                                    emotion=ai_result.emotion,
                                )
                                bp_cmd = build_image_command(
                                    ffmpeg_path=self.settings.ffmpeg_path,
                                    input_path=prompt_card_path,
                                    output_path=segment_path,
                                    ass_path=ass_path,
                                    duration=max(segment.duration, 0.5),
                                    width=width, height=height,
                                    version=version, segment_type=segment.type,
                                    camera=getattr(segment, 'camera', '静态') or '静态',
                                    visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                                    pace=getattr(segment, 'pace', '正常') or '正常',
                                    emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                                    subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                                )
                                _run(bp_cmd)
                                if segment_path.exists() and segment_path.stat().st_size > 0:
                                    shot_used = True
                                    warnings.append(
                                        f"AI prompt card for segment {segment.id} "
                                        f"(API key not configured, prompt ready for Seedance/Runway/Kling)"
                                    )
                            except Exception:
                                pass  # Fall through to packaging card below

                    if not shot_used and is_reference and segment.source != "reorder":
                        # Do NOT use reference video for non-reorder segments —
                        # it shows the wrong product. Generate a clean blueprint
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
                            camera=getattr(segment, 'camera', '静态') or '静态',
                            visual_fx=getattr(segment, 'visual_fx', '无') or '无',
                            pace=getattr(segment, 'pace', '正常') or '正常',
                            emotion=getattr(segment, 'emotion', '亲切') or '亲切',
                            subtitle_anim=getattr(segment, 'subtitle_anim', '淡入') or '淡入',
                        )
                    else:
                        start_seconds = (
                            segment.source_start if is_reference and segment.source_start is not None
                            else segment.start if is_reference
                            else 0.0
                        )
                        # ── Audio policy ──
                        # 1. Reference video: ALWAYS mute (new script ≠ old speech)
                        # 2. User-uploaded asset without TTS: keep original audio
                        # 3. User-uploaded asset with TTS: mute (TTS replaces original)
                        if is_reference:
                            keep_audio = False
                        else:
                            keep_audio = (not bool(self.settings.tts_api_key)
                                          and _has_audio_stream(source_path, self.settings.ffprobe_path))
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

            # ── TTS: per-segment synthesis, audio-driven duration (Pixelle-Video pattern) ──
            self.repository.update_render_job(job_id, progress=75, warnings=warnings)
            tts = TTSEngine(
                endpoint=self.settings.tts_endpoint or None,
                api_key=self.settings.tts_api_key,
                voice=self.settings.tts_voice,
                speed=self.settings.tts_speed,
                inference_mode="local" if not self.settings.tts_api_key else "api",
            )
            if tts.available:
                tts_ok_count = 0
                for idx, segment in enumerate(segments):
                    seg_text = _strip_production_params(segment.script or "")
                    if not seg_text.strip():
                        continue
                    seg_path = segment_files[idx]
                    seg_dur = max(segment.duration, 0.5)
                    tts_seg_path = work_dir / f"segment_{idx:03d}_tts.mp3"

                    # Per-segment TTS synthesis (audio drives duration)
                    if tts.synthesize(seg_text, tts_seg_path, target_duration=seg_dur):
                        tts_ok_count += 1
                        # Get actual audio duration → update segment duration
                        actual_dur = _probe_duration(tts_seg_path)
                        if actual_dur > 0:
                            segment.duration = max(actual_dur, 0.5)

                        # Smart merge: video + TTS audio
                        mixed_path = work_dir / f"segment_{idx:03d}_mixed.mp4"
                        _merge_video_audio_smart(
                            str(seg_path), str(tts_seg_path), str(mixed_path),
                            ffmpeg_path=self.settings.ffmpeg_path,
                        )
                        if mixed_path.exists() and mixed_path.stat().st_size > 0:
                            mixed_path.replace(seg_path)
                            segment_files[idx] = seg_path

                if tts_ok_count > 0:
                    # ── Reflow timeline after audio-driven duration changes ──
                    cursor = 0.0
                    for seg in segments:
                        seg.start = cursor
                        seg.duration = max(seg.duration, 0.5)
                        seg.end = cursor + seg.duration
                        cursor = seg.end
                    warnings.append(
                        f"TTS voiceover added ({tts_ok_count}/{len(segments)} segments, "
                        f"audio-driven duration, total={cursor:.1f}s)"
                    )
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

                # ── Beat alignment: snap segment transitions to BGM beats ──
                segment_starts = [s.start for s in segments]
                beats = bgm.detect_beats(bgm_track["path"], script.total_duration + 3)
                beat_snapped = 0
                if beats and len(beats) >= 2:
                    for seg in segments:
                        # Snap each segment's start to nearest beat within ±0.15s tolerance
                        seg_start = float(seg.start)
                        nearest = min(beats, key=lambda b: abs(b - seg_start))
                        if abs(nearest - seg_start) <= 0.15 and nearest != seg_start:
                            seg.start = nearest
                            beat_snapped += 1
                    if beat_snapped > 0:
                        warnings.append(f"Beat aligned: {beat_snapped}/{len(segments)} segment transitions synced")

                try:
                    cmd = bgm.mix_command(
                        input_video=concat_output,
                        bgm_path=bgm_track["path"],
                        output_video=bgm_output,
                        volume=getattr(self.settings, 'bgm_volume', 0.08),
                        duration=script.total_duration,
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
    emotion: str = "亲切",
    subtitle_anim: str = "淡入",
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type, emotion=emotion, subtitle_anim=subtitle_anim)
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


def _cinematic_motion(segment_type: str, width: int, height: int, duration: float, *, camera: str | None = None) -> str:
    """Generate per-segment camera motion using the LLM-assigned camera parameter.

    Falls back to segment-type-based defaults if camera is not specified.
    """
    d = max(duration, 1.0)
    base = f"d=1:s={width}x{height}:fps=30"

    # Dynamic motion from camera parameter (LLM-assigned, from audit optimization)
    cam = camera or ""
    if cam == "快推":
        return f"zoompan=z='min(zoom+0.001,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
    elif cam == "缓推":
        return f"zoompan=z='min(zoom+0.0005,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-1.0*on':{base}"
    elif cam == "拉远":
        return f"zoompan=z='max(zoom-0.0008,0.92)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-0.5*on':{base}"
    elif cam == "横移":
        return f"zoompan=z='min(zoom+0.0002,1.04)':x='iw/2-(iw/zoom/2)+3*sin(on*0.3)':y='ih/2-(ih/zoom/2)':{base}"
    elif cam == "跟随":
        return f"zoompan=z='min(zoom+0.0003,1.05)':x='iw/2-(iw/zoom/2)+1.5*on':y='ih/2-(ih/zoom/2)-0.5*on':{base}"
    elif cam == "手持微晃":
        return f"zoompan=z='min(zoom+0.0008*(0.5+0.5*sin(on*1.7)),1.06)':x='iw/2-(iw/zoom/2)+3*sin(on*2.1)':y='ih/2-(ih/zoom/2)+2*sin(on*1.9)':{base}"

    # Fallback: segment-type-based motion (backward compatibility) or "静态" camera
    if segment_type == "hook":
        return f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "pain":
        return f"zoompan=z='max(zoom-0.0002,0.95)':x='iw/2-(iw/zoom/2)+2*on':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "product":
        return f"zoompan=z='min(zoom+0.0005,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-1.5*on':{base}"
    elif segment_type == "proof":
        return f"zoompan=z='min(zoom+0.0003,1.04)':x='iw/2-(iw/zoom/2)+3*sin(on*0.3)':y='ih/2-(ih/zoom/2)':{base}"
    elif segment_type == "cta":
        return f"zoompan=z='min(zoom+0.001,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-3*on':{base}"
    else:
        return f"zoompan=z='min(zoom+0.0004,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"


def _apply_visual_fx(vf_filter: str, visual_fx: str, duration: float) -> str:
    """Apply LLM-assigned visual effects to the FFmpeg filter chain.

    - 震屏 → randomized crop offset
    - 闪白 → brightness flash at start
    - 慢动作 → PTS slowdown
    - 放大 → additional zoom layer
    - 模糊过渡 → boxblur at segment edges
    """
    if visual_fx == "震屏":
        # Simulate shake via high contrast + slight brightness boost.
        # (True per-frame crop shake avoided due to FFmpeg expression comma-parsing issues.)
        shake = "eq=contrast=1.25:brightness=0.06"
        return f"{vf_filter},{shake}" if vf_filter else shake
    elif visual_fx == "闪白":
        flash = f"eq=brightness='1+0.3*if(lt(t,{min(duration, 0.5)}),1,0)':contrast='1+0.1*if(lt(t,{min(duration, 0.5)}),1,0)'"
        return f"{vf_filter},{flash}" if vf_filter else flash
    elif visual_fx == "慢动作":
        slow = f"setpts=1.3*PTS" if duration > 2 else "setpts=1.1*PTS"
        return f"{vf_filter},{slow}" if vf_filter else slow
    elif visual_fx == "放大":
        zoom = "zoompan=z='min(zoom+0.002,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"
        return zoom  # replace existing zoompan, don't chain
    elif visual_fx == "模糊过渡":
        blur = f"boxblur=2:1"
        return f"{vf_filter},{blur}" if vf_filter else blur
    return vf_filter


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
    camera: str = "静态",
    visual_fx: str = "无",
    pace: str = "正常",
    emotion: str = "亲切",
    subtitle_anim: str = "淡入",
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type, emotion=emotion, subtitle_anim=subtitle_anim)
    # Use LLM-assigned camera motion (from audit optimization)
    if visual_fx == "放大":
        zoom_filter = _cinematic_motion(segment_type, width, height, duration, camera="快推")
    else:
        zoom_filter = _cinematic_motion(segment_type, width, height, duration, camera=camera)
    # Apply visual effects
    if visual_fx != "放大":
        zoom_filter = _apply_visual_fx(zoom_filter, visual_fx, duration)
    # Apply pace adjustment
    if pace == "快":
        zoom_filter = f"{zoom_filter},setpts=0.85*PTS" if zoom_filter else "setpts=0.85*PTS"
    elif pace == "慢":
        zoom_filter = f"{zoom_filter},setpts=1.2*PTS" if zoom_filter else "setpts=1.2*PTS"
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
    emotion: str = "亲切",
    subtitle_anim: str = "淡入",
) -> list[str]:
    output_duration = _output_duration(duration, version, segment_type)
    filters = _version_filters(width, height, ass_path, version, segment_type, emotion=emotion, subtitle_anim=subtitle_anim)
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
    ])
    # ── MUST explicitly map streams ──
    # Without -map, FFmpeg default selection picks 0:a (original audio) even
    # when a silent anullsrc is provided at input 1. This caused weeks of
    # audio overlap bugs where original audio mixed with TTS.
    if not has_audio:
        command.extend(["-map", "0:v", "-map", "1:a"])
    command.extend([
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


def _version_filters(width: int, height: int, ass_path: Path, version: str, segment_type: str, *, emotion: str = "亲切", subtitle_anim: str = "淡入") -> str:
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
    ]
    # Version-specific enhancements
    if version == "strong_hook" and segment_type == "hook":
        filters.extend([
            "setpts=0.77*PTS",
            f"zoompan=z='min(zoom+0.0015,1.08)':d=1:s={width}x{height}:fps=30",
            "eq=contrast=1.12",
        ])
    if version == "strong_conversion" and segment_type == "cta":
        filters.extend(["tpad=stop_mode=clone:stop_duration=2", "drawbox=x=60:y=80:w=520:h=150:color=white@0.88:t=fill"])

    # ── Emotion → color grading (was a dead parameter) ──
    emotion_eq = _emotion_color_grade(emotion)
    if emotion_eq:
        filters.append(emotion_eq)

    # ── Subtitle anim → ASS effect tags (was a dead parameter) ──
    # Applied via ASS template; the _ass_for_segment function now reads this param.
    filters.append(f"subtitles='{_ffmpeg_filter_path(ass_path)}'")
    filters.append("format=yuv420p")
    return ",".join(filters)


def _emotion_color_grade(emotion: str) -> str | None:
    """Convert LLM-assigned emotion to FFmpeg eq filter for color grading."""
    grades = {
        "惊讶": "eq=contrast=1.15:saturation=1.2",
        "紧迫": "eq=contrast=1.1:brightness=0.05:saturation=1.1",
        "亲切": "eq=contrast=0.95:saturation=1.05:brightness=0.02",
        "权威": "eq=contrast=1.05:saturation=0.9:brightness=-0.02",
        "感动": "eq=contrast=0.9:saturation=1.1:brightness=0.03",
        "兴奋": "eq=contrast=1.1:saturation=1.3:brightness=0.05",
        "平静": "eq=contrast=0.95:saturation=0.85",
    }
    return grades.get(emotion)


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

    # ── Subtitle animation from LLM-assigned subtitle_anim (was a dead parameter) ──
    anim = getattr(segment, 'subtitle_anim', '淡入') or '淡入'
    anim_tag = ""
    seg_dur = duration if duration is not None else segment.duration
    anim_ms = int(min(seg_dur * 1000 * 0.3, 400))  # animate over first 30% of duration, max 400ms
    if anim == "弹入":
        # Bounce scale-in
        anim_tag = r"{\t(0," + str(anim_ms) + r",\fscx120\fscy120)}"
    elif anim == "逐字出现":
        # No ASS native support — use a reveal tag approximation
        anim_tag = r"{\t(0,800,\alpha&HFF&\alpha&H00&)}"
    elif anim == "缩放出现":
        anim_tag = r"{\t(0," + str(anim_ms) + r",\fscx120\fscy120)}"
    elif anim == "无动画":
        anim_tag = ""
    # 淡入 = default (no tag needed, natural fade from ASS renderer)

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00F5F5F5,&H000000FF,&H00181818,&H66000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{_ass_time(seg_dur)},Default,,0,0,0,,{anim_tag}{text}
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


def _probe_duration(file_path: str | Path) -> float:
    """Get media duration via ffprobe. Returns 0.0 on failure."""
    import json as _json
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(file_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return float(_json.loads(result.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError):
        return 0.0


def _merge_video_audio_smart(
    video_path: str, audio_path: str, output_path: str,
    *,
    ffmpeg_path: str = "ffmpeg",
    pad_strategy: str = "freeze",
    audio_volume: float = 0.9,
) -> None:
    """Smart video+audio merge: freeze last frame if audio is longer.

    Ported from Pixelle-Video's VideoService.merge_audio_video().
    - audio > video → pad video (freeze last frame)
    - video > audio within 0.3s → acceptable, keep as-is
    - video >> audio → trim video to match audio
    """
    video_dur = _probe_duration(video_path)
    audio_dur = _probe_duration(audio_path)
    diff = video_dur - audio_dur
    target_dur = max(video_dur, audio_dur, 0.5)

    if diff >= -0.3:
        # Video >= audio (or slightly shorter within tolerance): simple merge
        cmd = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex",
            f"[1:a]volume={audio_volume}[tts];[0:a][tts]amix=inputs=2:duration=first",
            "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    else:
        # Audio longer than video → pad video (freeze last frame)
        pad_dur = -diff
        cmd = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={pad_dur:.3f}[v];"
            f"[1:a]volume={audio_volume}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-shortest", output_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


from services.frame_renderer import _render_prompt_card_html


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
