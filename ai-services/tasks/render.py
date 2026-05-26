from __future__ import annotations

from config import Settings
from models.repository import SQLiteRepository
from services.compositor import Compositor
from tasks.celery_app import celery_app


@celery_app.task(name="tasks.render_video_task")
def render_video_task(
    job_id: str,
    project_id: str,
    version: str,
    resolution: str,
    script_version: str | None = None,
) -> None:
    settings = Settings()
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()
    Compositor(repository, settings).render(
        job_id=job_id,
        project_id=project_id,
        version=version,
        resolution=resolution,
        script_version=script_version,
    )


def dispatch_render_task(
    job_id: str,
    project_id: str,
    version: str,
    resolution: str,
    script_version: str | None = None,
) -> None:
    render_video_task.delay(job_id, project_id, version, resolution, script_version)
