from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import GapFixAllResponse, GapFixRequest, GapFixResponse, GapListResponse
from routes.assets import _to_asset_out
from services.gap_detector import GapDetector, GapNotFoundError
from services.gap_filler import GapFiller, GapFixError
from services.structure_editor import StructureNotFoundError


def build_gaps_router(repository: SQLiteRepository, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/gaps", tags=["gaps"])
    detector = GapDetector(repository)
    filler = GapFiller(repository, settings)

    @router.get("/{project_id}", response_model=GapListResponse)
    async def list_gaps(project_id: str) -> dict[str, Any]:
        try:
            return {"gaps": detector.detect(project_id)}
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/{project_id}/fix", response_model=GapFixResponse)
    async def fix_gap(project_id: str, payload: GapFixRequest) -> dict[str, Any]:
        try:
            return _format_fix_result(filler.fix(project_id, payload.gap_id, payload.strategy))
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GapNotFoundError, GapFixError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/{project_id}/fix-all", response_model=GapFixAllResponse)
    async def fix_all_gaps(project_id: str) -> dict[str, Any]:
        try:
            result = filler.fix_all(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GapNotFoundError, GapFixError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            **result,
            "details": [_format_fix_result(detail) for detail in result["details"]],
            "assets": [_to_asset_out(asset) for asset in result["assets"]],
        }

    return router


def _format_fix_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "assets": [_to_asset_out(asset) for asset in result.get("assets", [])],
    }
