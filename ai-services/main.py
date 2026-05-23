from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import AnalyzeResponse, TaskProgress
from routes.assets import build_assets_router
from routes.projects import build_projects_router
from routes.structure import build_structure_router
from services.uploads import (
    UploadValidationError,
    new_job_id,
    save_upload_bytes,
    validate_upload_metadata,
)
from tasks.analyze import dispatch_analyze_task


API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = Settings()
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()

    app = FastAPI(title="StructForge AI Services", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_projects_router(repository, settings))
    app.include_router(build_structure_router(repository))
    app.include_router(build_assets_router(repository, settings))

    @app.get("/")
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(f"{API_PREFIX}/analyze", response_model=AnalyzeResponse)
    async def analyze_video(
        video: UploadFile = File(...),
        project_id: str | None = Form(default=None),
    ) -> AnalyzeResponse:
        content = await video.read()
        try:
            validate_upload_metadata(
                content_type=video.content_type,
                filename=video.filename,
                size_bytes=len(content),
                settings=settings,
            )
        except UploadValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        job_id = new_job_id()
        source_path = save_upload_bytes(content, job_id=job_id, settings=settings)
        repository.create_job(job_id=job_id, source_path=str(source_path), project_id=project_id)
        if project_id:
            repository.upsert_project(project_id=project_id, status="analyzing")

        try:
            dispatch_analyze_task(job_id, str(source_path))
        except Exception as exc:
            repository.fail_job(job_id, str(exc), stage="Failed to dispatch analysis task")
            raise HTTPException(status_code=503, detail="Failed to dispatch analysis task") from exc

        return AnalyzeResponse(job_id=job_id)

    @app.get(f"{API_PREFIX}/analyze/{{job_id}}", response_model=TaskProgress)
    async def get_analysis(job_id: str) -> TaskProgress:
        job = repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        return TaskProgress(
            status=job["status"],
            progress=job["progress"],
            stage=job["stage"],
            result=job["result"],
            error=job["error"],
        )

    return app


app = create_app()
