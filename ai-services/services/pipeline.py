from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import Settings

log = logging.getLogger(__name__)
from models.repository import SQLiteRepository
from models.schemas import JobStatus, VideoStructure
from services.asr import transcribe_video
from services.llm_structure import (
    DoubaoSeedClient,
    LocalStructureClient,
    extract_structure_with_retries,
)
from services.media import detect_scenes, extract_keyframes, probe_video
from services.reference_assets import bind_reference_video_asset
from services.vision import analyze_frames
from services.cover_generator import CoverGenerator
from services.highlight_detector import HighlightDetector
from services.structure_cache import StructureCache


class AnalysisPipeline:
    def __init__(self, *, settings: Settings, repository: SQLiteRepository) -> None:
        self.settings = settings
        self.repository = repository

    def run(self, job_id: str, source_path: str | Path) -> VideoStructure:
        path = Path(source_path)
        try:
            self._progress(job_id, 5, "Inspecting media tools")
            meta = probe_video(path, self.settings)

            # Check structure cache — skip full analysis if we've seen this video before.
            cache_fingerprint: str | None = None
            try:
                cache = StructureCache()
                # Read first + last 4KB as content sample for unique fingerprinting
                content_sample = b""
                try:
                    with open(path, "rb") as f:
                        content_sample = f.read(4096)
                        if path.stat().st_size > 8192:
                            f.seek(-4096, 2)
                            content_sample += f.read(4096)
                except Exception:
                    pass
                cache_fingerprint = cache.fingerprint(
                    duration=float(meta["duration"]),
                    resolution=str(meta["resolution"]),
                    scene_count=0,
                    audio_segment_count=0,
                    file_size=path.stat().st_size,
                    content_sample=content_sample,
                )
                cached = cache.get(cache_fingerprint)
                if cached is not None:
                    self._progress(job_id, 95, "Using cached analysis")
                    # Bind reference video asset before completing.
                    job = self.repository.get_job(job_id)
                    if job and job.get("project_id"):
                        project = self.repository.get_project(job["project_id"])
                        if project and not project.get("reference_job_id"):
                            cached = bind_reference_video_asset(
                                self.repository,
                                project_id=job["project_id"],
                                job_id=job_id,
                                source_path=str(path),
                                structure=cached,
                            )
                    self.repository.complete_job(job_id, cached)
                    return cached
            except Exception:
                cache_fingerprint = None

            self._progress(job_id, 25, "Detecting scene boundaries")
            scenes = detect_scenes(path, float(meta["duration"]), self.settings)

            self._progress(job_id, 40, "Extracting keyframes")
            frames = extract_keyframes(path, job_id, scenes, float(meta["duration"]), self.settings)

            self._progress(job_id, 55, "Transcribing speech")
            asr_result = transcribe_video(path, job_id, self.settings)
            asr_text = str(asr_result.get("text", ""))
            asr_segments = asr_result.get("segments", [])

            self._progress(job_id, 70, "Analyzing visual frames")
            vision_result = analyze_frames(frames, self.settings)
            vision_tags: list[str] = []
            vision_descs: list[str] = []
            vision_ocr_texts: list[str] = []
            vision_product_types: list[str] = []
            for f in (vision_result.get("frames") or [])[:5]:
                vision_tags.extend(f.get("tags", []))
                vision_descs.append(f.get("description", ""))
                for t in f.get("ocr", []):
                    if t.strip():
                        vision_ocr_texts.append(t.strip())
                pt = f.get("product_type", "")
                if pt:
                    vision_product_types.append(pt)

            # Write diagnostics
            import sys
            diag = f"\n=== STRUCTFORGE DIAG ===\nASR({len(asr_text)}chars): {asr_text[:200]}\nVISION TAGS: {vision_tags[:10]}\nVISION OCR: {vision_ocr_texts[:5]}\nVISION PRODUCT: {vision_product_types[:3]}\n=== END DIAG ===\n"
            sys.stderr.write(diag)
            sys.stderr.flush()

            self._progress(job_id, 85, "Extracting frontend video structure")
            context = self._context(meta, scenes, frames, asr_result, vision_result)
            client = (
                DoubaoSeedClient(self.settings)
                if self.settings.doubao_llm_endpoint and self.settings.doubao_llm_api_key
                else LocalStructureClient(context)
            )
            structure = extract_structure_with_retries(
                client=client,
                prompt_context=context,
                max_attempts=self.settings.llm_max_attempts,
            )

            # Store ASR + Vision raw data alongside structure for burst audit
            vision_frames_raw = vision_result.get("frames", []) if vision_result else []
            asr_data = asr_result if asr_result else {}
            self.repository.complete_job(
                job_id, structure,
                vision_frames=vision_frames_raw,
                asr_data=asr_data,
            )

            # Bind reference video for compositor
            job = self.repository.get_job(job_id)
            if job and job.get("project_id"):
                project = self.repository.get_project(job["project_id"])
                if project and not project.get("reference_job_id"):
                    structure = bind_reference_video_asset(
                        self.repository,
                        project_id=job["project_id"],
                        job_id=job_id,
                        source_path=str(path),
                        structure=structure,
                    )

            # Non-blocking: cache result for future runs.
            if cache_fingerprint:
                try:
                    cache = StructureCache()
                    cache.put(cache_fingerprint, structure)
                except Exception:
                    pass

            # Store shot pool metadata for video recombination during rendering.
            try:
                shot_pool = []
                for i, scene in enumerate(scenes):
                    frame_data = vision_result.get("frames", [{}])
                    frame = frame_data[i] if i < len(frame_data) else {}
                    shot_pool.append({
                        "start_ms": scene.get("start_ms", 0),
                        "end_ms": scene.get("end_ms", 0),
                        "start_s": scene.get("start_s", scene.get("start_ms", 0) / 1000),
                        "end_s": scene.get("end_s", scene.get("end_ms", 0) / 1000),
                        "duration_ms": scene.get("duration_ms", 0),
                        "duration_s": round((scene.get("end_ms", 0) - scene.get("start_ms", 0)) / 1000, 2),
                        "tags": frame.get("tags", []),
                        "scene_type": frame.get("scene_type", ""),
                    })
                existing = self.repository.get_job(job_id)
                if existing and existing.get("result"):
                    result_with_pool = dict(existing["result"])
                    result_with_pool["shot_pool"] = shot_pool
                    self.repository.update_job(job_id, result=result_with_pool)
            except Exception:
                pass

            # Non-blocking: generate cover image and detect highlights after analysis completes.
            try:
                cover_gen = CoverGenerator(self.settings)
                cover_path = cover_gen.generate(structure, keyframe_paths=frames, product_name="")
                existing = self.repository.get_job(job_id)
                if existing and existing.get("result"):
                    result_with_cover = dict(existing["result"])
                    meta = dict(result_with_cover.get("meta") or {})
                    meta["coverImagePath"] = str(cover_path)
                    result_with_cover["meta"] = meta
                    self.repository.update_job(job_id, result=result_with_cover)
            except Exception:
                pass

            try:
                detector = HighlightDetector(
                    llm_endpoint=self.settings.doubao_llm_endpoint,
                    llm_api_key=self.settings.doubao_llm_api_key,
                    llm_model=self.settings.doubao_llm_model,
                )
                highlights = detector.detect(
                    rhythm_points=[p.model_dump(mode="json") for p in structure.rhythm],
                    asr_segments=asr_result.get("segments", []),
                    vision_frames=vision_result.get("frames", []),
                    duration=float(meta["duration"]),
                )
                if highlights:
                    existing = self.repository.get_job(job_id)
                    if existing and existing.get("result"):
                        result_with_hl = dict(existing["result"])
                        result_with_hl["highlightMoments"] = highlights
                        self.repository.update_job(job_id, result=result_with_hl)
            except Exception:
                pass

            return structure
        except Exception as exc:
            self.repository.fail_job(job_id, str(exc))
            raise

    def _progress(self, job_id: str, progress: int, stage: str) -> None:
        self.repository.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=progress,
            stage=stage,
        )

    def _context(
        self,
        meta: dict[str, Any],
        scenes: list[dict[str, int]],
        frames: list[Path],
        asr_result: dict[str, Any],
        vision_result: dict[str, Any],
    ) -> dict[str, Any]:
        asr_text = str(asr_result.get("text", ""))

        # Collect OCR text from vision frames
        vision_ocr_all: list[str] = []
        vision_product_types: list[str] = []
        for f in (vision_result.get("frames") or []):
            for t in f.get("ocr", []):
                if t.strip() and t.strip() not in vision_ocr_all:
                    vision_ocr_all.append(t.strip())
            pt = f.get("product_type", "")
            if pt and pt not in vision_product_types:
                vision_product_types.append(pt)

        return {
            "meta": {
                "duration": meta["duration"],
                "resolution": meta["resolution"],
                "frame_rate": meta.get("frame_rate"),
                "codec": meta.get("codec"),
                "shots": len(scenes),
            },
            "asr_available": len(asr_text) > 5,
            "asr_is_empty": len(asr_text) == 0,
            "scenes": scenes,
            "frames": [str(frame) for frame in frames],
            "asr": asr_result,
            "vision": vision_result,
            # Summaries for easy LLM consumption
            "vision_ocr_text": vision_ocr_all,
            "vision_product_type": vision_product_types,
        }
