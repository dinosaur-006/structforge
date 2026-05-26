from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from main import create_app
from models.repository import SQLiteRepository
from tests.test_schemas import valid_video_structure_payload


def test_assets_schema_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "structforge.db"
    repository = SQLiteRepository(db_path)
    repository.initialize()
    repository.initialize()

    with repository.engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))}

    assert {
        "id",
        "project_id",
        "name",
        "type",
        "file_path",
        "tag",
        "match_status",
        "match_score",
        "analysis_json",
        "origin",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_asset_uploads_return_frontend_safe_assets_and_match_matrix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    monkeypatch.setenv("STRUCTFORGE_UPLOAD_DIR", str(tmp_path / "uploads"))
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    client = TestClient(create_app())

    uploads = [
        ("conflict.png", b"fake-image", "image/png"),
        ("product-demo.mp4", b"fake-video", "video/mp4"),
        ("offer.txt", "限时优惠 立即购买 Logo 行动".encode("utf-8"), "text/plain"),
    ]
    asset_ids: list[str] = []
    for filename, content, content_type in uploads:
        response = client.post(
            "/api/v1/assets/analyze/proj-1",
            files={"file": (filename, content, content_type)},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["asset_id"]
        assert payload["analysis"]["description"]
        asset_ids.append(payload["asset_id"])

    listed = client.get("/api/v1/assets/proj-1")
    assert listed.status_code == 200
    assets = listed.json()
    assert len(assets) == 3
    assert {asset["type"] for asset in assets} == {"image", "video", "text"}
    assert set(assets[0]) == {"id", "name", "type", "tag", "matchStatus", "matchScore", "color", "origin", "recommendedSegments", "reason"}
    assert {asset["origin"] for asset in assets} == {"uploaded"}

    matrix = client.get("/api/v1/assets/proj-1/match")
    assert matrix.status_code == 200
    matches = matrix.json()["matches"]
    assert len(matches) == len(asset_ids) * len(valid_video_structure_payload()["script"])

    hook_scores = [match["score"] for match in matches if match["segment_id"] == "seg-1"]
    cta_scores = [match["score"] for match in matches if match["segment_id"] == "seg-3"]
    assert max(hook_scores) >= 80
    assert max(cta_scores) >= 80

    matched_assets = client.get("/api/v1/assets/proj-1").json()
    assert any(asset["matchStatus"] == "matched" for asset in matched_assets)
    cta_asset = next(asset for asset in matched_assets if asset["name"] == "offer.txt")
    assert cta_asset["recommendedSegments"][0]["segmentId"] == "seg-3"
    assert "CTA" in cta_asset["reason"]


def test_empty_analysis_json_asset_stays_unmatched(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    asset = repository.create_asset(
        project_id="proj-1",
        name="empty.png",
        asset_type="image",
        file_path=str(tmp_path / "empty.png"),
        tag="",
        analysis={},
    )

    from services.asset_matcher import AssetMatcher

    matches = AssetMatcher(repository).match_project_assets("proj-1")

    assert all(match["score"] == 0 for match in matches if match["asset_id"] == asset["id"])
    assert repository.list_assets("proj-1")[0]["match_status"] == "unmatched"


def test_asset_routes_validate_project_and_file_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    monkeypatch.setenv("STRUCTFORGE_UPLOAD_DIR", str(tmp_path / "uploads"))
    client = TestClient(create_app())

    missing_project = client.post(
        "/api/v1/assets/analyze/missing",
        files={"file": ("asset.png", b"fake-image", "image/png")},
    )
    invalid_type = client.post(
        "/api/v1/assets/analyze/missing",
        files={"file": ("asset.pdf", b"fake-pdf", "application/pdf")},
    )
    empty_file = client.post(
        "/api/v1/assets/analyze/missing",
        files={"file": ("asset.png", b"", "image/png")},
    )

    assert missing_project.status_code == 404
    assert invalid_type.status_code == 400
    assert empty_file.status_code == 400


def test_project_delete_removes_assets_and_project_upload_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    monkeypatch.setenv("STRUCTFORGE_UPLOAD_DIR", str(tmp_path / "uploads"))
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-1", name="Headphones", status="draft")
    project_asset_dir = tmp_path / "uploads" / "proj-1" / "assets"
    project_asset_dir.mkdir(parents=True)
    asset_path = project_asset_dir / "asset.txt"
    asset_path.write_text("优惠购买", encoding="utf-8")
    repository.create_asset(
        project_id="proj-1",
        name="asset.txt",
        asset_type="text",
        file_path=str(asset_path),
        tag="优惠购买",
        analysis={"description": "优惠购买", "tags": ["优惠", "购买"]},
    )
    client = TestClient(create_app())

    response = client.delete("/api/v1/projects/proj-1")

    assert response.status_code == 204
    assert repository.list_assets("proj-1") == []
    assert not (tmp_path / "uploads" / "proj-1").exists()
