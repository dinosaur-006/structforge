from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol

from fastapi import APIRouter, HTTPException

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import RenderJobResponse, RenderProgress, RenderRequest
from services.compositor import Compositor


class RenderCompositor(Protocol):
    def render(self, *, job_id: str, project_id: str, version: str, resolution: str) -> None:
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
    runner = background_runner or _thread_runner

    @router.post("/{project_id}", response_model=RenderJobResponse)
    async def start_render(project_id: str, payload: RenderRequest) -> dict[str, str]:
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not project.get("script"):
            raise HTTPException(status_code=422, detail="Project has no FinalScript")

        job = repository.create_render_job(project_id=project_id, version=payload.version)

        def run() -> None:
            compositor = compositor_factory() if compositor_factory else Compositor(repository, settings)
            compositor.render(
                job_id=job["id"],
                project_id=project_id,
                version=payload.version,
                resolution=payload.resolution,
            )

        runner(run)
        return {"job_id": job["id"]}

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
