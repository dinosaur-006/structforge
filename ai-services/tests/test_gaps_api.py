from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app
from models.repository import SQLiteRepository
from services.asset_matcher import AssetMatcher
from tests.test_schemas import valid_video_structure_payload


def _seed_project(tmp_path: Path, monkeypatch) -> TestClient:
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
    return TestClient(create_app())


def _repository(tmp_path: Path) -> SQLiteRepository:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    return repository


def test_chinese_asset_matching_keywords_are_stable(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    for tag in ["冲突画面", "产品特写", "优惠购买"]:
        repository.create_asset(
            project_id="proj-1",
            name=f"{tag}.txt",
            asset_type="text",
            file_path=None,
            tag=tag,
            analysis={"description": tag, "tags": [tag], "ocr_text": tag},
        )

    matches = AssetMatcher(repository).match_project_assets("proj-1")

    assert max(match["score"] for match in matches if match["segment_id"] == "seg-1") >= 80
    assert max(match["score"] for match in matches if match["segment_id"] == "seg-3") >= 80


def test_gap_detection_returns_all_segments_without_assets(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)

    response = client.get("/api/v1/gaps/proj-1")

    assert response.status_code == 200
    gaps = response.json()["gaps"]
    assert {gap["segmentId"] for gap in gaps} == {"seg-1", "seg-2", "seg-3"}
    assert next(gap for gap in gaps if gap["segmentId"] == "seg-1")["severity"] == "critical"
    assert next(gap for gap in gaps if gap["segmentId"] == "seg-3")["severity"] == "critical"
    assert set(gaps[0]) == {
        "id",
        "segmentId",
        "severity",
        "description",
        "requiredSlot",
        "selectedStrategyId",
        "recommendedStrategy",
        "strategies",
        "status",
    }


def test_gap_detection_skips_segments_with_matching_assets(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)
    response = client.post(
        "/api/v1/assets/analyze/proj-1",
        files={"file": ("conflict.txt", "冲突画面 悬念 特写".encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200

    gaps = client.get("/api/v1/gaps/proj-1").json()["gaps"]

    assert "seg-1" not in {gap["segmentId"] for gap in gaps}
    assert {"seg-2", "seg-3"}.issubset({gap["segmentId"] for gap in gaps})


def test_packaging_fix_adds_asset_updates_structure_and_closes_gap(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)
    gap = next(gap for gap in client.get("/api/v1/gaps/proj-1").json()["gaps"] if gap["segmentId"] == "seg-1")

    response = client.post("/api/v1/gaps/proj-1/fix", json={"gap_id": gap["id"], "strategy": "packaging"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "fixed"
    assert payload["updated_structure"]["script"][0]["assetId"]
    assert all(gap["id"] != payload["gap_id"] for gap in payload["gaps"])
    assets = client.get("/api/v1/assets/proj-1").json()
    assert any(asset["type"] == "image" and asset["matchStatus"] == "matched" for asset in assets)
    assert (tmp_path / "uploads" / "proj-1" / "assets").exists()


def test_fix_all_rechecks_after_each_fix_and_closes_all_gaps(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)

    response = client.post("/api/v1/gaps/proj-1/fix-all")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixed_count"] == 3
    assert payload["gaps"] == []
    assert len(payload["details"]) == 3
    assert all(segment.get("assetId") for segment in payload["updated_structure"]["script"])


def test_aigc_and_recompose_fallback_to_packaging_without_external_services(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)
    gap = client.get("/api/v1/gaps/proj-1").json()["gaps"][0]

    response = client.post("/api/v1/gaps/proj-1/fix", json={"gap_id": gap["id"], "strategy": "aigc"})

    assert response.status_code == 200
    assert response.json()["status"] == "fixed"


def test_gap_routes_validate_errors(tmp_path: Path, monkeypatch) -> None:
    client = _seed_project(tmp_path, monkeypatch)

    missing_project = client.get("/api/v1/gaps/missing")
    unknown_gap = client.post("/api/v1/gaps/proj-1/fix", json={"gap_id": "gap-missing", "strategy": "packaging"})
    invalid_strategy = client.post("/api/v1/gaps/proj-1/fix", json={"gap_id": "gap-seg-1", "strategy": "bad"})

    assert missing_project.status_code == 404
    assert unknown_gap.status_code == 400
    assert invalid_strategy.status_code == 400
