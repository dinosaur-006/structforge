from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from services.projects import ProjectNotFoundError, ProjectService
from services.vision import analyze_frames


def build_projects_router(repository: SQLiteRepository, settings: Settings | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
    service = ProjectService(
        repository,
        upload_dir=settings.upload_dir if settings else None,
        output_dir=settings.output_dir if settings else None,
    )

    @router.post("", response_model=ProjectOut)
    async def create_project(payload: ProjectCreate) -> dict:
        return service.create_project(
            name=payload.name,
            description=payload.description,
            brief=payload.brief.model_dump(mode="json"),
        )

    @router.get("", response_model=list[ProjectOut])
    async def list_projects() -> list[dict]:
        return service.list_projects()

    @router.get("/{project_id}", response_model=ProjectOut)
    async def get_project(project_id: str) -> dict:
        try:
            return service.get_project(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @router.put("/{project_id}", response_model=ProjectOut)
    async def update_project(project_id: str, payload: ProjectUpdate) -> dict:
        try:
            return service.update_project(
                project_id,
                name=payload.name,
                description=payload.description,
                brief=payload.brief.model_dump(mode="json") if payload.brief is not None else None,
            )
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @router.delete("/{project_id}", status_code=204)
    async def delete_project(project_id: str) -> Response:
        try:
            service.delete_project(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        return Response(status_code=204)

    @router.post("/{project_id}/product-image")
    async def analyze_product_image(project_id: str, file: UploadFile = File(...)):
        """Analyze a product photo using Vision API. Returns visual tags for prompt generation.

        The analysis result (tags, colors, description) can be stored in project
        metadata and used by the PromptEngine to generate more accurate Flux prompts.
        """
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files accepted")

        _settings = settings or Settings()
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

        # Save temporarily
        suffix = Path(file.filename or "product.png").suffix or ".png"
        tmp = Path(tempfile.gettempdir()) / f"sf_product_{project_id}{suffix}"
        tmp.write_bytes(content)

        try:
            vision = analyze_frames([tmp], _settings)
            frames = vision.get("frames", [])
            if not frames:
                return {"status": "skipped", "tags": [], "colors": [], "description": ""}

            f0 = frames[0]
            result = {
                "status": "ok",
                "tags": f0.get("tags", []),
                "colors": f0.get("dominant_colors", []),
                "description": f0.get("description", ""),
                "product_type": f0.get("product_type", ""),
                "ocr": f0.get("ocr", []),
            }
            # Store in project brief metadata
            project = repository.get_project(project_id)
            if project:
                brief = dict(project.get("brief") or {})
                brief["_productVisual"] = result
                repository.update_project(project_id, brief=brief)
            return result
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200], "tags": [], "colors": [], "description": ""}
        finally:
            tmp.unlink(missing_ok=True)

    return router
