from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol

from fastapi import APIRouter, HTTPException, Response

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
                )

            (background_runner or _thread_runner)(run)
        else:
            try:
                dispatch_render_task(
                    job["id"],
                    project_id,
                    payload.version,
                    payload.resolution,
                    payload.script_version,
                )
            except Exception as exc:
                repository.update_render_job(job["id"], status="failed", progress=100, error="Failed to dispatch render task")
                raise HTTPException(status_code=503, detail="Failed to dispatch render task") from exc
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

    return router
