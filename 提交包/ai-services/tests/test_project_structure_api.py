from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from main import create_app
from models.repository import SQLiteRepository
from tests.test_schemas import valid_video_structure_payload


def test_project_api_crud_returns_frontend_safe_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    client = TestClient(create_app())

    created = client.post(
        "/api/v1/projects",
        json={
            "name": "Headphone launch",
            "description": "Q3 push",
            "brief": {
                "productName": "Quiet Pro",
                "sellingPoints": ["降噪", "轻盈"],
                "targetAudience": "通勤人士",
                "offer": "到手价 299 元",
                "tone": "专业",
                "mandatoryClaims": [],
            },
        },
    )
    assert created.status_code == 200
    project = created.json()
    assert set(project) == {"id", "name", "description", "brief", "status", "updatedAt"}
    assert project["status"] == "draft"
    assert project["brief"]["productName"] == "Quiet Pro"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == project["id"]
    assert "analysis_result_json" not in listed.json()[0]

    updated = client.put(f"/api/v1/projects/{project['id']}", json={"name": "Updated"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated"

    deleted = client.delete(f"/api/v1/projects/{project['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404


def test_project_api_requires_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    client = TestClient(create_app())

    response = client.post("/api/v1/projects", json={"description": "Missing name"})

    assert response.status_code == 422


def test_structure_api_editing_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    db_path = tmp_path / "structforge.db"
    repository = SQLiteRepository(db_path)
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    client = TestClient(create_app())

    structure = client.get("/api/v1/structure/proj-1")
    assert structure.status_code == 200
    assert set(structure.json()) == {"meta", "script", "rhythm", "packaging", "health"}

    added = client.post(
        "/api/v1/structure/proj-1/segment",
        json={
            "type": "proof",
            "label": "Extra proof",
            "start": 18,
            "end": 21,
            "duration": 3,
            "goal": "prove",
            "copy": "Proof line",
            "visual": "Demo shot",
        },
    )
    assert added.status_code == 200
    new_segment_id = added.json()["script"][-1]["id"]

    updated = client.put(
        f"/api/v1/structure/proj-1/segment/{new_segment_id}",
        json={"copy": "Updated line"},
    )
    assert updated.status_code == 200
    assert updated.json()["script"][-1]["copy"] == "Updated line"

    order = [segment["id"] for segment in reversed(updated.json()["script"])]
    reordered = client.put("/api/v1/structure/proj-1/reorder", json={"order": order})
    assert reordered.status_code == 200
    assert [segment["id"] for segment in reordered.json()["script"]] == order

    bad_reorder = client.put("/api/v1/structure/proj-1/reorder", json={"order": order[:-1]})
    assert bad_reorder.status_code == 400

    undo = client.post("/api/v1/structure/proj-1/undo")
    assert undo.status_code == 200
    assert undo.json()["action"] == "undo"
    assert "structure" in undo.json()


def test_structure_api_empty_undo_returns_complete_structure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    client = TestClient(create_app())

    response = client.post("/api/v1/structure/proj-1/undo")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["structure"]["meta"]["duration"] == 35.0


def test_multiple_samples_require_explicit_reference_switch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-1", name="Headphones", status="analyzing")
    first = valid_video_structure_payload()
    second = deepcopy(first)
    second["script"][0]["copy"] = "Second reference hook"

    repository.create_job("job-1", "sample-one.mp4", project_id="proj-1")
    repository.complete_job("job-1", first)
    edited = deepcopy(first)
    edited["script"][0]["copy"] = "User edited hook"
    repository.save_project_structure_state("proj-1", current_structure=edited, undo_stack=[], redo_stack=[])
    repository.create_job("job-2", "sample-two.mp4", project_id="proj-1")
    repository.complete_job("job-2", second)

    client = TestClient(create_app())
    samples = client.get("/api/v1/analyze/project/proj-1/samples")
    structure_before = client.get("/api/v1/structure/proj-1")
    selected = client.put("/api/v1/analyze/project/proj-1/reference/job-2")
    structure_after = client.get("/api/v1/structure/proj-1")

    assert samples.status_code == 200
    assert [sample["job_id"] for sample in samples.json()] == ["job-1", "job-2"]
    assert samples.json()[0]["isReference"] is True
    assert structure_before.json()["script"][0]["copy"] == "User edited hook"
    assert selected.status_code == 200
    assert selected.json()["job_id"] == "job-2"
    assert selected.json()["isReference"] is True
    assert structure_after.json()["script"][0]["copy"] == "Second reference hook"
    assert all(segment["assetId"] for segment in structure_after.json()["script"])
