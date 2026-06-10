from __future__ import annotations

import importlib.util

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
import json as _json_module


class UTF8JSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return _json_module.dumps(content, ensure_ascii=False, allow_nan=False).encode("utf-8")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import AnalysisSampleOut, AnalyzeResponse, CapabilityStatusOut, TaskProgress
from routes.assets import build_assets_router
from routes.gaps import build_gaps_router
from routes.migrate import build_migrate_router
from routes.projects import build_projects_router
from routes.optimize import build_optimize_router
from routes.render import build_render_router
from routes.structure import build_structure_router
from services.uploads import (
    UploadValidationError,
    new_job_id,
    save_upload_bytes,
    validate_upload_metadata,
)
from services.reference_assets import bind_reference_video_asset
from seed import seed_if_empty
from tasks.analyze import dispatch_analyze_task


API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = Settings()
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()

    # Auto-seed a demo project on first startup when enabled.
    seed_if_empty(settings)

    app = FastAPI(title="StructForge AI Services", version="0.1.0", default_response_class=UTF8JSONResponse)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Optional API key authentication.
    from services.auth import APIKeyMiddleware
    if settings.api_key:
        app.add_middleware(APIKeyMiddleware, api_key=settings.api_key)

    # ── Global exception handler for LLM failures ──
    from services.llm_client import LLMError

    @app.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        """Catch LLMError and return structured 503 so the frontend can show LLMOutagePanel."""
        return JSONResponse(
            status_code=503,
            content=exc.to_dict(),
        )

    app.include_router(build_projects_router(repository, settings))
    app.include_router(build_structure_router(repository, settings))
    app.include_router(build_assets_router(repository, settings))
    app.include_router(build_gaps_router(repository, settings))
    app.include_router(build_migrate_router(repository, settings=settings))
    app.include_router(build_render_router(repository, settings))
    app.include_router(build_optimize_router(repository, settings))
    from routes.audit_api import build_audit_router
    app.include_router(build_audit_router(repository, settings))
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

    @app.get("/")
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/generation/{slot_id}")
    async def ws_generation(websocket: WebSocket, slot_id: str) -> None:
        """WebSocket endpoint for real-time AIGC generation progress."""
        from services.generation_notifier import get_notifier
        notifier = get_notifier()
        await notifier.connect(slot_id, websocket)
        try:
            while True:
                # Keep connection alive; client sends pings
                await websocket.receive_text()
        except WebSocketDisconnect:
            await notifier.disconnect(slot_id)
        except Exception:
            await notifier.disconnect(slot_id)

    @app.get(f"{API_PREFIX}/capabilities", response_model=CapabilityStatusOut)
    async def capabilities() -> CapabilityStatusOut:
        whisper_available = importlib.util.find_spec("whisperx") is not None
        asr_configured = bool(settings.volcano_asr_endpoint and settings.volcano_asr_api_key)
        vision_configured = bool(
            (settings.doubao_vision_endpoint and settings.doubao_vision_api_key)
            or (settings.doubao_llm_endpoint and settings.doubao_llm_api_key)
        )
        return CapabilityStatusOut(
            llm={
                "state": "configured" if settings.doubao_llm_endpoint and settings.doubao_llm_api_key else "fallback",
                "label": "Doubao LLM",
                "detail": "已提供 LLM 配置；首次真实生成时验证授权可用性"
                if settings.doubao_llm_endpoint and settings.doubao_llm_api_key
                else "分析使用本地结构回退，脚本生成需配置模型",
            },
            vision={
                "state": "configured" if vision_configured else "fallback",
                "label": "Vision",
                "detail": "Lite 多模态关键帧与素材理解已配置；首次真实分析时验证授权可用性"
                if vision_configured
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
                "state": "configured" if (settings.doubao_image_api_key or getattr(settings, 'runninghub_api_key', None)) else "disabled",
                "label": "AIGC",
                "detail": "ComfyUI Flux 文生图已配置"
                if getattr(settings, 'runninghub_api_key', None)
                else "Seedream AI 图片生成已配置"
                if settings.doubao_image_api_key
                else "未配置图片生成，使用 Prompt Card 占位补全",
            },
            videoGeneration={
                "state": "configured" if getattr(settings, 'runninghub_api_key', None) and getattr(settings, 'comfyui_video_enabled', False) else "disabled",
                "label": "AI 视频生成",
                "detail": "RunningHub WAN 2.2 图生视频已启用"
                if getattr(settings, 'runninghub_api_key', None) and getattr(settings, 'comfyui_video_enabled', False)
                else "RunningHub WAN 2.2 未启用 (设置 STRUCTFORGE_COMFYUI_VIDEO_ENABLED=true)"
                if getattr(settings, 'runninghub_api_key', None)
                else "未配置 RunningHub API Key",
            },
            taskExecution={
                "state": "inline" if settings.celery_task_always_eager else "worker",
                "label": "Tasks",
                "detail": "本地同步任务模式" if settings.celery_task_always_eager else "Redis / Celery 异步任务模式",
            },
        )

    @app.post(f"{API_PREFIX}/media/preview")
    async def media_preview(prompt: str = Form(...), width: int = Form(512), height: int = Form(512)):
        """Preview media generation — test a single image before full render."""
        from services.comfyui_service import create_comfyui_service
        import asyncio as _asyncio

        svc = create_comfyui_service(settings)
        if not svc.available:
            raise HTTPException(status_code=503, detail="ComfyUI not configured")

        try:
            result = await _asyncio.wait_for(
                svc.generate_image(prompt=prompt, width=width, height=height),
                timeout=60,
            )
            return {"status": "completed", "url": result.get("url", ""), "prompt": prompt[:200]}
        except _asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Preview timed out (60s)")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Preview failed: {exc}")

    @app.get(f"{API_PREFIX}/diagnostics/llm")
    async def llm_diagnostics() -> dict[str, object]:
        """Active LLM connectivity test — pings the configured endpoint with a minimal prompt."""
        import time as _time
        import httpx as _httpx

        endpoint = settings.doubao_llm_endpoint
        api_key = settings.doubao_llm_api_key
        model = settings.doubao_llm_model

        if not endpoint or not api_key:
            return {
                "status": "unconfigured",
                "endpoint": endpoint or "(not set)",
                "message": "LLM endpoint or API key not configured. Set STRUCTFORGE_DOUBAO_LLM_ENDPOINT and STRUCTFORGE_DOUBAO_LLM_API_KEY in .env",
            }

        t0 = _time.monotonic()
        try:
            resp = _httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": "回复 ok"}], "max_tokens": 4},
                timeout=settings.llm_timeout_seconds,
            )
            elapsed = round(_time.monotonic() - t0, 2)
            resp.raise_for_status()
            return {
                "status": "healthy",
                "endpoint": endpoint,
                "model": model,
                "latency_seconds": elapsed,
                "timeout_seconds": settings.llm_timeout_seconds,
                "message": f"LLM responded in {elapsed}s",
            }
        except _httpx.ReadTimeout:
            elapsed = round(_time.monotonic() - t0, 2)
            return {
                "status": "timeout",
                "endpoint": endpoint,
                "model": model,
                "latency_seconds": elapsed,
                "timeout_seconds": settings.llm_timeout_seconds,
                "message": f"LLM timed out after {elapsed}s (limit: {settings.llm_timeout_seconds}s). Consider increasing STRUCTFORGE_LLM_TIMEOUT_SECONDS or checking network.",
            }
        except Exception as exc:
            elapsed = round(_time.monotonic() - t0, 2)
            return {
                "status": "error",
                "endpoint": endpoint,
                "model": model,
                "latency_seconds": elapsed,
                "error": str(exc),
                "message": f"LLM connectivity test failed: {exc}",
            }

    @app.get(f"{API_PREFIX}/pipelines")
    async def list_pipelines():
        """List available rendering pipelines (Pixelle-Video pattern)."""
        from services.pipeline_registry import registry as _reg
        return [
            {"name": s.name, "display_name": s.display_name, "icon": s.icon,
             "description": s.description, "tags": s.tags,
             "requires_comfyui": s.requires_comfyui, "requires_tts": s.requires_tts}
            for s in _reg.list()
        ]

    @app.get(f"{API_PREFIX}/templates")
    async def list_templates():
        """List available HTML templates with metadata (Pixelle-Video pattern)."""
        from services.template_util import list_templates as _list
        return _list()

    @app.post(f"{API_PREFIX}/image/generate")
    async def generate_image(prompt: str = Form(...), width: int = Form(1080), height: int = Form(1920)):
        """Generate an AI image via ComfyUI RunningHub Flux. Falls back to error if not configured."""
        from services.comfyui_service import create_comfyui_service
        import asyncio as _asyncio

        svc = create_comfyui_service(settings)
        if not svc.available:
            raise HTTPException(status_code=503, detail="ComfyUI RunningHub not configured. Set STRUCTFORGE_RUNNINGHUB_API_KEY in .env")

        try:
            result = await _asyncio.wait_for(
                svc.generate_image(prompt=prompt, width=width, height=height),
                timeout=120,
            )
            return {"status": "completed", "url": result.get("url", "")}
        except _asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Image generation timed out (120s)")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}")

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
            dispatch_analyze_task(job_id, str(source_path), settings=settings)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            repository.fail_job(job_id, str(exc), stage="Failed to dispatch analysis task")
            raise HTTPException(status_code=503, detail=f"分析任务启动失败: {exc}") from exc

        return AnalyzeResponse(job_id=job_id)

    @app.get(f"{API_PREFIX}/analyze/{{job_id}}", response_model=TaskProgress)
    async def get_analysis(job_id: str) -> TaskProgress:
        job = repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        # Strip internal fields that aren't part of VideoStructure schema
        result = job.get("result")
        if isinstance(result, dict):
            result = {k: v for k, v in result.items() if not k.startswith("_")}

        return TaskProgress(
            status=job["status"],
            progress=job["progress"],
            stage=job["stage"],
            result=result,
            error=job["error"],
        )

    @app.get(f"{API_PREFIX}/analyze/{{job_id}}/stream")
    async def stream_analysis(job_id: str):
        """SSE endpoint: pushes real-time progress updates."""
        import asyncio

        async def event_stream():
            last_progress = -1
            for _ in range(300):  # Max 5 minutes
                job = repository.get_job(job_id)
                if job is None:
                    yield f"data: {{'error': 'Job not found'}}\n\n"
                    return
                current = job.get("progress", 0)
                if current != last_progress:
                    import json as _json
                    yield f"data: {_json.dumps({'progress': current, 'stage': job.get('stage',''), 'status': job.get('status','')}, ensure_ascii=False)}\n\n"
                    last_progress = current
                if job["status"] in ("completed", "failed"):
                    return
                await asyncio.sleep(1)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get(f"{API_PREFIX}/analyze/project/{{project_id}}/samples", response_model=list[AnalysisSampleOut])
    async def list_analysis_samples(project_id: str) -> list[AnalysisSampleOut]:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        results = []
        for job in repository.list_project_jobs(project_id):
            r = job.get("result")
            if isinstance(r, dict):
                r = {k: v for k, v in r.items() if not k.startswith("_")}
            results.append(AnalysisSampleOut(
                job_id=job["job_id"], status=job["status"],
                progress=job["progress"], stage=job["stage"],
                result=r, isReference=job.get("isReference", False),
            ))
        return results

    @app.put(f"{API_PREFIX}/analyze/project/{{project_id}}/reference/{{job_id}}", response_model=AnalysisSampleOut)
    async def select_analysis_reference(project_id: str, job_id: str) -> AnalysisSampleOut:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        candidate = repository.get_job(job_id)
        selected_structure = None
        if candidate and candidate.get("project_id") == project_id and candidate.get("result"):
            selected_structure = bind_reference_video_asset(
                repository,
                project_id=project_id,
                job_id=job_id,
                source_path=candidate["source_path"],
                structure=candidate["result"],
            )
        job = repository.select_reference_job(project_id, job_id, selected_structure)
        if job is None:
            raise HTTPException(status_code=404, detail="Completed sample not found")
        r = job.get("result")
        if isinstance(r, dict):
            r = {k: v for k, v in r.items() if not k.startswith("_")}
        return AnalysisSampleOut(
            job_id=job["job_id"],
            status=job["status"],
            progress=job["progress"],
            stage=job["stage"],
            result=r,
            isReference=True,
        )

    return app


app = create_app()
