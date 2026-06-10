from __future__ import annotations

from pathlib import Path

from models.repository import SQLiteRepository
from models.schemas import VideoStructure


def bind_reference_video_asset(
    repository: SQLiteRepository,
    *,
    project_id: str,
    job_id: str,
    source_path: str,
    structure: VideoStructure | dict,
    fill_unbound_only: bool = False,
) -> VideoStructure:
    asset = next(
        (
            item
            for item in repository.list_assets(project_id)
            if (item.get("analysis") or {}).get("reference_job_id") == job_id
            and (item.get("analysis") or {}).get("reference_source") is True
        ),
        None,
    )
    if asset is None:
        asset = repository.create_asset(
            project_id=project_id,
            name=f"参考样例原片 - {Path(source_path).name}",
            asset_type="video",
            file_path=source_path,
            tag="参考样例原片",
            analysis={
                "asset_status": "analyzed",
                "analysis_type": "video",
                "description": "参考样例原片，可按分镜时间区间复用真实画面",
                "tags": ["参考样例原片"],
                "reference_source": True,
                "reference_job_id": job_id,
            },
            origin="uploaded",
        )

    payload = VideoStructure.model_validate(structure).model_dump(mode="json", by_alias=True)
    for segment in payload["script"]:
        if not fill_unbound_only or not segment.get("assetId"):
            segment["assetId"] = asset["id"]
    return VideoStructure.model_validate(payload)
