from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from models.repository import SQLiteRepository
from models.schemas import ReorderRequest, StructureActionResponse, VideoStructure
from services.structure_editor import (
    ReorderValidationError,
    SegmentNotFoundError,
    StructureEditor,
    StructureNotFoundError,
)


def build_structure_router(repository: SQLiteRepository) -> APIRouter:
    router = APIRouter(prefix="/api/v1/structure/{project_id}", tags=["structure"])
    editor = StructureEditor(repository)

    @router.get("", response_model=VideoStructure)
    async def get_structure(project_id: str) -> VideoStructure:
        try:
            return editor.get_structure(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("", response_model=VideoStructure)
    async def replace_structure(project_id: str, payload: VideoStructure) -> VideoStructure:
        try:
            return editor.replace_structure(project_id, payload.model_dump(mode="json", by_alias=True))
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/segment", response_model=VideoStructure)
    async def add_segment(project_id: str, payload: dict[str, Any] = Body(...)) -> VideoStructure:
        try:
            return editor.add_segment(project_id, payload)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/segment/{segment_id}", response_model=VideoStructure)
    async def update_segment(
        project_id: str,
        segment_id: str,
        payload: dict[str, Any] = Body(...),
    ) -> VideoStructure:
        try:
            return editor.update_segment(project_id, segment_id, payload)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SegmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/segment/{segment_id}", response_model=VideoStructure)
    async def delete_segment(project_id: str, segment_id: str) -> VideoStructure:
        try:
            return editor.delete_segment(project_id, segment_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SegmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/reorder", response_model=VideoStructure)
    async def reorder_segments(project_id: str, payload: ReorderRequest) -> VideoStructure:
        try:
            return editor.reorder_segments(project_id, payload.order)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReorderValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/undo", response_model=StructureActionResponse)
    async def undo(project_id: str) -> dict:
        try:
            result = editor.undo(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "action": result.action,
            "available": result.available,
            "structure": result.structure,
        }

    @router.post("/redo", response_model=StructureActionResponse)
    async def redo(project_id: str) -> dict:
        try:
            result = editor.redo(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "action": result.action,
            "available": result.available,
            "structure": result.structure,
        }

    @router.post("/reset", response_model=VideoStructure)
    async def reset(project_id: str) -> VideoStructure:
        try:
            return editor.reset(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
