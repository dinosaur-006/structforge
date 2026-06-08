from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import AssetAnalyzeResponse, AssetMatchResponse, AssetOut
from services.asset_analyzer import (
    AssetAnalyzer,
    AssetProjectNotFoundError,
    AssetValidationError,
)
from services.asset_matcher import AssetMatcher
from services.structure_editor import StructureNotFoundError


PALETTE = ["#5C8B67", "#C87D53", "#7C8BBD", "#D4A24E", "#4A8C6F", "#C85555"]


def build_assets_router(repository: SQLiteRepository, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/assets", tags=["assets"])
    analyzer = AssetAnalyzer(repository, settings)
    matcher = AssetMatcher(
        repository,
        llm_endpoint=settings.doubao_llm_endpoint,
        llm_api_key=settings.doubao_llm_api_key,
        llm_model=settings.doubao_llm_model,
    )

    @router.post("/analyze/{project_id}", response_model=AssetAnalyzeResponse)
    async def analyze_asset(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        try:
            asset = analyzer.analyze_upload(project_id, file, content)
        except AssetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AssetProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        return {"asset_id": asset["id"], "analysis": asset["analysis"]}

    @router.get("/{project_id}", response_model=list[AssetOut])
    async def list_assets(project_id: str) -> list[dict[str, Any]]:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            recommendations = matcher.recommend_project_assets(project_id)
        except StructureNotFoundError:
            recommendations = {}
        return [_to_asset_out(asset, recommendations.get(asset["id"])) for asset in repository.list_assets(project_id)]

    @router.get("/{project_id}/{asset_id}/thumbnail")
    async def get_asset_thumbnail(project_id: str, asset_id: str):
        asset = repository.get_asset(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        file_path = asset.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="No file for asset")
        path = Path(file_path) if not isinstance(file_path, Path) else file_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="Asset file not found")
        return FileResponse(str(path), media_type="image/png" if path.suffix.lower() == ".png" else "image/jpeg")

    @router.get("/{project_id}/match", response_model=AssetMatchResponse)
    async def match_assets(project_id: str) -> dict[str, Any]:
        try:
            matches = matcher.match_project_assets(project_id)
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"matches": matches}

    return router


def _to_asset_out(asset: dict[str, Any], recommendation: dict[str, Any] | None = None) -> dict[str, Any]:
    explanation = recommendation or {
        "recommendedSegments": [],
        "reason": "等待结构初始化后生成匹配推荐",
    }
    return {
        "id": asset["id"],
        "name": asset["name"],
        "type": asset["type"],
        "tag": asset.get("tag") or "素材",
        "matchStatus": asset.get("match_status") or "unmatched",
        "matchScore": float(asset.get("match_score") or 0),
        "color": _color_for_label(asset.get("tag") or asset["name"]),
        "origin": asset.get("origin") or "uploaded",
        **explanation,
    }


def _color_for_label(label: str) -> str:
    index = sum(ord(character) for character in label) % len(PALETTE)
    return PALETTE[index]
