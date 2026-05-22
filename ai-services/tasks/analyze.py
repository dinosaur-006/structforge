from __future__ import annotations

from config import Settings
from models.repository import SQLiteRepository
from services.pipeline import AnalysisPipeline
from tasks.celery_app import celery_app


@celery_app.task(name="tasks.analyze_video_task")
def analyze_video_task(job_id: str, source_path: str) -> dict:
    settings = Settings()
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()
    pipeline = AnalysisPipeline(settings=settings, repository=repository)
    structure = pipeline.run(job_id, source_path)
    return structure.model_dump(mode="json")


def dispatch_analyze_task(job_id: str, source_path: str) -> None:
    analyze_video_task.delay(job_id, source_path)
