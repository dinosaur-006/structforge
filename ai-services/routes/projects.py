from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from services.projects import ProjectNotFoundError, ProjectService


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

    return router
