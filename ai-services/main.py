from __future__ import annotations

import importlib.util

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import AnalysisSampleOut, AnalyzeResponse, CapabilityStatusOut, TaskProgress
from routes.assets import build_assets_router
from routes.gaps import build_gaps_router
from routes.migrate import build_migrate_router
from routes.projects import build_projects_router
from routes.render import build_render_router
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
    app.include_router(build_gaps_router(repository, settings))
    app.include_router(build_migrate_router(repository, settings=settings))
    app.include_router(build_render_router(repository, settings))
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

    @app.get("/")
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/capabilities", response_model=CapabilityStatusOut)
    async def capabilities() -> CapabilityStatusOut:
        whisper_available = importlib.util.find_spec("whisperx") is not None
        asr_configured = bool(settings.volcano_asr_endpoint and settings.volcano_asr_api_key)
        return CapabilityStatusOut(
            llm={
                "state": "configured" if settings.doubao_llm_endpoint and settings.doubao_llm_api_key else "fallback",
                "label": "Doubao LLM",
                "detail": "已提供 LLM 配置；首次真实生成时验证授权可用性"
                if settings.doubao_llm_endpoint and settings.doubao_llm_api_key
                else "分析使用本地结构回退，脚本生成需配置模型",
            },
            vision={
                "state": "configured" if settings.doubao_vision_endpoint and settings.doubao_vision_api_key else "fallback",
                "label": "Vision",
                "detail": "真实关键帧与素材画面理解已配置"
                if settings.doubao_vision_endpoint and settings.doubao_vision_api_key
                else "使用占位画面描述",
            },
            asr={
                "state": "configured" if asr_configured or whisper_available else "disabled",
                "label": "ASR",
                "detail": "火山语音识别已配置"
                if asr_configured
                else "WhisperX 本地转写可用"
                if whisper_available
                else "未启用语音转写",
            },
            aigc={
                "state": "configured" if settings.jimeng_image_endpoint and settings.jimeng_image_api_key else "disabled",
                "label": "AIGC",
                "detail": "即梦图片补全已配置"
                if settings.jimeng_image_endpoint and settings.jimeng_image_api_key
                else "未配置生成图片，补全策略不可选",
            },
            taskExecution={
                "state": "inline" if settings.celery_task_always_eager else "worker",
                "label": "Tasks",
                "detail": "本地同步任务模式" if settings.celery_task_always_eager else "Redis / Celery 异步任务模式",
            },
        )

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

    @app.get(f"{API_PREFIX}/analyze/project/{{project_id}}/samples", response_model=list[AnalysisSampleOut])
    async def list_analysis_samples(project_id: str) -> list[AnalysisSampleOut]:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return [
            AnalysisSampleOut(
                job_id=job["job_id"],
                status=job["status"],
                progress=job["progress"],
                stage=job["stage"],
                result=job["result"],
                isReference=job["isReference"],
            )
            for job in repository.list_project_jobs(project_id)
        ]

    @app.put(f"{API_PREFIX}/analyze/project/{{project_id}}/reference/{{job_id}}", response_model=AnalysisSampleOut)
    async def select_analysis_reference(project_id: str, job_id: str) -> AnalysisSampleOut:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        job = repository.select_reference_job(project_id, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Completed sample not found")
        return AnalysisSampleOut(
            job_id=job["job_id"],
            status=job["status"],
            progress=job["progress"],
            stage=job["stage"],
            result=job["result"],
            isReference=True,
        )

    return app


app = create_app()
