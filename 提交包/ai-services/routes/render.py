from __future__ import annotations

import asyncio as _asyncio
import json as _json
import threading
from collections.abc import Callable
from typing import Protocol

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import RenderJobResponse, RenderProgress, RenderRequest
from services.compositor import Compositor
from tasks.render import dispatch_render_task


class RenderCompositor(Protocol):
    def render(self, *, job_id: str, project_id: str, version: str, resolution: str, script_version: str | None = None) -> None:
        ...


def _thread_runner(fn: Callable[[], None]) -> None:
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()


def build_render_router(
    repository: SQLiteRepository,
    settings: Settings,
    *,
    compositor_factory: Callable[[], RenderCompositor] | None = None,
    background_runner: Callable[[Callable[[], None]], None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/render", tags=["render"])
    @router.post("/{project_id}", response_model=RenderJobResponse)
    async def start_render(project_id: str, payload: RenderRequest) -> dict[str, str]:
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not project.get("script"):
            raise HTTPException(status_code=422, detail="Project has no FinalScript")
        if payload.script_version and repository.get_script_version(project_id, payload.script_version) is None:
            raise HTTPException(status_code=422, detail="Requested script version has not been generated")

        job = repository.create_render_job(project_id=project_id, version=payload.version)

        if compositor_factory or background_runner:
            def run() -> None:
                compositor = compositor_factory() if compositor_factory else Compositor(repository, settings)
                compositor.render(
                    job_id=job["id"],
                    project_id=project_id,
                    version=payload.version,
                    resolution=payload.resolution,
                    script_version=payload.script_version,
                    segment_modes=payload.segment_modes,
                )

            (background_runner or _thread_runner)(run)
        else:
            # Always run render in a separate thread to avoid event loop conflicts
            # (ComfyUI calls need their own event loop)
            def _run_in_thread():
                try:
                    dispatch_render_task(
                        job["id"], project_id,
                        payload.version, payload.resolution,
                        payload.script_version,
                    )
                except Exception as exc:
                    err_msg = str(exc)[:500]
                    repository.update_render_job(job["id"], status="failed", progress=100, error=err_msg)

            _thread_runner(_run_in_thread)
        return {"job_id": job["id"]}

    @router.delete("/{job_id}", status_code=204)
    async def cancel_render(job_id: str):
        job = repository.get_render_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Render job not found")
        if job["status"] in ("pending", "processing"):
            repository.update_render_job(job_id, status="failed", progress=100, error="Cancelled by user")
        return Response(status_code=204)

    @router.get("/{job_id}", response_model=RenderProgress)
    async def get_render_job(job_id: str) -> dict:
        job = repository.get_render_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Render job not found")
        return {
            "status": job["status"],
            "progress": job["progress"],
            "output_url": job.get("output_path"),
            "error": job.get("error"),
            "warnings": job.get("warnings") or [],
        }

    @router.get("/{job_id}/stream")
    async def stream_render(job_id: str):
        """SSE endpoint for real-time render progress (Pixelle-Video ProgressEvent pattern)."""
        async def event_stream():
            last_progress = -1
            for _ in range(600):  # Max 10 minutes
                job = repository.get_render_job(job_id)
                if job is None:
                    yield f"data: {_json.dumps({'error': 'Job not found'}, ensure_ascii=False)}\n\n"
                    return
                current = job.get("progress", 0)
                stage = job.get("stage", "")
                status = job.get("status", "")
                warnings = job.get("warnings") or []
                if current != last_progress or status != "processing":
                    yield f"data: {_json.dumps({'progress': current, 'stage': stage, 'status': status, 'warnings': warnings[-3:]}, ensure_ascii=False)}\n\n"
                    last_progress = current
                if status in ("completed", "failed"):
                    return
                await _asyncio.sleep(1)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @router.post("/{project_id}/upgrade-to-video/{segment_index}")
    async def upgrade_segment_to_video(project_id: str, segment_index: int):
        """Phase 2: Upgrade an AI-generated image segment to AI video via WAN 2.2.

        Uses the Flux-generated PNG as first frame for WAN 2.2 image-to-video.
        Returns a task_id for polling via /upgrade-status/{task_id}.
        """
        import uuid as _uuid
        from services.comfyui_service import create_comfyui_service

        svc = create_comfyui_service(settings)
        if not svc.available:
            raise HTTPException(status_code=503, detail="ComfyUI not configured")

        # Find the Flux image for this segment
        import glob as _glob
        work_dir = settings.output_dir / project_id
        patterns = [
            str(work_dir / f".work-*" / f"segment_{segment_index:03d}_flux.png"),
            str(work_dir / f".work-*" / f"segment_{segment_index:03d}_promptcard.png"),
        ]
        image_path = None
        for pattern in patterns:
            matches = sorted(_glob.glob(pattern))
            if matches:
                image_path = matches[0]
                break

        if not image_path:
            # Generate a new image first if none exists
            raise HTTPException(status_code=404,
                detail=f"No image found for segment {segment_index}. Render Phase 1 first.")

        task_id = str(_uuid.uuid4())[:8]

        # Store task info (in-memory for now; can move to DB later)
        if not hasattr(settings, '_video_upgrade_tasks'):
            settings._video_upgrade_tasks = {}  # type: ignore[attr-defined]
        settings._video_upgrade_tasks[task_id] = {  # type: ignore[attr-defined]
            "status": "running",
            "project_id": project_id,
            "segment_index": segment_index,
            "started_at": str(_asyncio.get_event_loop().time()),
        }

        # Launch async video generation
        async def _generate():
            try:
                result = await svc.generate_video(
                    prompt="product showcase video, cinematic lighting, smooth camera movement",
                    image_path=image_path,
                    width=1080, height=1920, duration=3,
                )
                settings._video_upgrade_tasks[task_id] = {  # type: ignore[attr-defined]
                    "status": "completed",
                    "video_url": result.get("url", ""),
                }
            except Exception as exc:
                settings._video_upgrade_tasks[task_id] = {  # type: ignore[attr-defined]
                    "status": "failed",
                    "error": str(exc),
                }

        _asyncio.create_task(_generate())
        return {"task_id": task_id, "status": "running"}

    @router.get("/upgrade-status/{task_id}")
    async def get_upgrade_status(task_id: str):
        """Poll Phase 2 video upgrade task status."""
        tasks = getattr(settings, '_video_upgrade_tasks', {})
        task = tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    return router
