from __future__ import annotations

from pathlib import Path
from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import JobStatus, VideoStructure
from services.asr import transcribe_video
from services.llm_structure import (
    DoubaoSeedClient,
    LocalStructureClient,
    extract_structure_with_retries,
)
from services.media import detect_scenes, extract_keyframes, probe_video
from services.vision import analyze_frames


class AnalysisPipeline:
    def __init__(self, *, settings: Settings, repository: SQLiteRepository) -> None:
        self.settings = settings
        self.repository = repository

    def run(self, job_id: str, source_path: str | Path) -> VideoStructure:
        path = Path(source_path)
        try:
            self._progress(job_id, 5, "Inspecting media tools")
            meta = probe_video(path, self.settings)

            self._progress(job_id, 25, "Detecting scene boundaries")
            scenes = detect_scenes(path, float(meta["duration"]), self.settings)

            self._progress(job_id, 40, "Extracting keyframes")
            frames = extract_keyframes(path, job_id, scenes, float(meta["duration"]), self.settings)

            self._progress(job_id, 55, "Transcribing speech")
            asr_result = transcribe_video(path, job_id, self.settings)

            self._progress(job_id, 70, "Analyzing visual frames")
            vision_result = analyze_frames(frames, self.settings)

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
            self.repository.complete_job(job_id, structure)
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
        return {
            "meta": {
                "duration": meta["duration"],
                "resolution": meta["resolution"],
                "frame_rate": meta.get("frame_rate"),
                "codec": meta.get("codec"),
                "shots": len(scenes),
            },
            "scenes": scenes,
            "frames": [str(frame) for frame in frames],
            "asr": asr_result,
            "vision": vision_result,
        }
