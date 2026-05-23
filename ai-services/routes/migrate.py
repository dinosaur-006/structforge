from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript, MigrateRequest, MigrateVariantRequest
from services.llm_structure import JsonCompletionClient
from services.migrator import MigrationError, MigrationInputError, MigrationNotFoundError, MigratorService


def build_migrate_router(
    repository: SQLiteRepository,
    settings: Settings | None = None,
    client: JsonCompletionClient | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/migrate", tags=["migrate"])
    service = MigratorService(repository, settings=settings, client=client)

    @router.get("/{project_id}", response_model=FinalScript)
    async def get_script(project_id: str) -> FinalScript:
        try:
            script = service.get_saved_script(project_id)
        except MigrationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        if script is None:
            raise HTTPException(status_code=404, detail="Final script not found")
        return script

    @router.post("/{project_id}/variant", response_model=FinalScript)
    async def generate_variant(project_id: str, payload: MigrateVariantRequest) -> FinalScript:
        return _generate_or_raise(service, project_id, payload.style)

    @router.post("/{project_id}", response_model=FinalScript)
    async def generate_script(
        project_id: str,
        payload: MigrateRequest = Body(default_factory=MigrateRequest),
    ) -> FinalScript:
        return _generate_or_raise(service, project_id, payload.style)

    return router


def _generate_or_raise(service: MigratorService, project_id: str, style: str) -> FinalScript:
    try:
        return service.generate(project_id, style=style)  # type: ignore[arg-type]
    except MigrationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except MigrationInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MigrationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
