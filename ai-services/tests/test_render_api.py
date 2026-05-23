from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from config import Settings
from models.repository import SQLiteRepository
from routes.render import build_render_router
from tests.test_schemas import valid_video_structure_payload


class FakeCompositor:
    def __init__(self, repository: SQLiteRepository, settings: Settings, *, fail: bool = False) -> None:
        self.repository = repository
        self.settings = settings
        self.fail = fail
        self.calls: list[dict[str, str]] = []

    def render(self, *, job_id: str, project_id: str, version: str, resolution: str) -> None:
        self.calls.append({"job_id": job_id, "project_id": project_id, "version": version, "resolution": resolution})
        self.repository.update_render_job(job_id, status="processing", progress=35)
        if self.fail:
            self.repository.update_render_job(job_id, status="failed", progress=100, error="ffmpeg failed: codec missing")
            return
        output_dir = self.settings.output_dir / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{version}.mp4"
        output_path.write_bytes(b"fake mp4")
        self.repository.update_render_job(
            job_id,
            status="completed",
            progress=100,
            output_path=f"/outputs/{project_id}/{version}.mp4",
            warnings=["missing asset asset-1, used placeholder"],
        )


def inline_runner(fn) -> None:
    fn()


def test_render_jobs_schema_migration_and_repository_methods(tmp_path: Path) -> None:
    db_path = tmp_path / "structforge.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE render_jobs ("
                "id TEXT PRIMARY KEY, "
                "project_id TEXT NOT NULL, "
                "version TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "progress REAL NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
        )

    repository = SQLiteRepository(db_path)
    repository.initialize()
    repository.initialize()

    with repository.engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(render_jobs)"))}

    assert {"output_path", "error", "warnings_json"}.issubset(columns)

    job = repository.create_render_job(project_id="proj-1", version="strong_hook")
    repository.update_render_job(job["id"], status="processing", progress=42, warnings=["started"])
    loaded = repository.get_render_job(job["id"])

    assert loaded is not None
    assert loaded["status"] == "processing"
    assert loaded["progress"] == 42
    assert loaded["warnings"] == ["started"]


def test_render_routes_create_complete_and_poll_job(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    fake = FakeCompositor(repository, settings)
    client = render_client(repository, settings, fake)

    created = client.post("/api/v1/render/proj-1", json={"version": "strong_hook", "resolution": "1080p"})
    polled = client.get(f"/api/v1/render/{created.json()['job_id']}")

    assert created.status_code == 200
    assert polled.status_code == 200
    payload = polled.json()
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["output_url"] == "/outputs/proj-1/strong_hook.mp4"
    assert payload["warnings"] == ["missing asset asset-1, used placeholder"]
    assert fake.calls[0]["version"] == "strong_hook"


def test_render_routes_return_expected_errors(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-no-script", name="Project", description="Info", current_structure=valid_video_structure_payload())
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    client = render_client(repository, settings, FakeCompositor(repository, settings))

    assert client.post("/api/v1/render/missing", json={"version": "original"}).status_code == 404
    assert client.post("/api/v1/render/proj-no-script", json={"version": "original"}).status_code == 422
    assert client.get("/api/v1/render/job-missing").status_code == 404


def test_render_failure_is_visible_in_polling_response(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    client = render_client(repository, settings, FakeCompositor(repository, settings, fail=True))

    created = client.post("/api/v1/render/proj-1", json={"version": "strong_conversion"})
    polled = client.get(f"/api/v1/render/{created.json()['job_id']}")

    assert polled.json()["status"] == "failed"
    assert "codec missing" in polled.json()["error"]


def test_project_delete_removes_render_outputs(tmp_path: Path) -> None:
    from services.projects import ProjectService

    repository = seeded_repository(tmp_path)
    output_dir = tmp_path / "outputs"
    project_output_dir = output_dir / "proj-1"
    project_output_dir.mkdir(parents=True)
    (project_output_dir / "original.mp4").write_bytes(b"video")

    service = ProjectService(repository, upload_dir=tmp_path / "uploads", output_dir=output_dir)
    service.delete_project("proj-1")

    assert not project_output_dir.exists()


def render_client(repository: SQLiteRepository, settings: Settings, fake: FakeCompositor) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_render_router(
            repository,
            settings,
            compositor_factory=lambda: fake,
            background_runner=inline_runner,
        )
    )
    return TestClient(app)


def seeded_repository(tmp_path: Path) -> SQLiteRepository:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Project",
        description="Useful product information",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    repository.save_project_script("proj-1", final_script_payload())
    return repository


def final_script_payload() -> dict[str, Any]:
    return {
        "version": "high_click",
        "total_duration": 8,
        "segments": [
            {
                "id": "seg-1",
                "type": "hook",
                "start": 0,
                "end": 3,
                "duration": 3,
                "script": "Generated hook",
                "visual": "Black background",
                "asset_id": None,
                "subtitle_style": "clean_caption",
                "transition": "hard_cut",
                "locked": False,
            },
            {
                "id": "seg-2",
                "type": "cta",
                "start": 3,
                "end": 8,
                "duration": 5,
                "script": "Generated CTA",
                "visual": "Offer card",
                "asset_id": None,
                "subtitle_style": "clean_caption",
                "transition": "hard_cut",
                "locked": False,
            },
        ],
        "metadata": {"warnings": []},
    }
