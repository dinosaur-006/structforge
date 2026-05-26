from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript
from routes.render import build_render_router
from services.result_evaluator import ResultEvaluator
from tests.test_schemas import valid_video_structure_payload


class FakeCompositor:
    def __init__(self, repository: SQLiteRepository, settings: Settings, *, fail: bool = False) -> None:
        self.repository = repository
        self.settings = settings
        self.fail = fail
        self.calls: list[dict[str, str]] = []

    def render(self, *, job_id: str, project_id: str, version: str, resolution: str, script_version: str | None = None) -> None:
        self.calls.append({"job_id": job_id, "project_id": project_id, "version": version, "resolution": resolution, "script_version": script_version or ""})
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
    script = final_script_payload()
    repository.save_script_version("proj-1", script, ResultEvaluator().evaluate_script(FinalScript.model_validate(script)))
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    fake = FakeCompositor(repository, settings)
    client = render_client(repository, settings, fake)

    created = client.post("/api/v1/render/proj-1", json={"version": "strong_hook", "resolution": "1080p", "script_version": "high_click"})
    polled = client.get(f"/api/v1/render/{created.json()['job_id']}")

    assert created.status_code == 200
    assert polled.status_code == 200
    payload = polled.json()
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["output_url"] == "/outputs/proj-1/strong_hook.mp4"
    assert payload["warnings"] == ["missing asset asset-1, used placeholder"]
    assert fake.calls[0]["version"] == "strong_hook"
    assert fake.calls[0]["script_version"] == "high_click"


def test_render_routes_return_expected_errors(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-no-script", name="Project", description="Info", current_structure=valid_video_structure_payload())
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    client = render_client(repository, settings, FakeCompositor(repository, settings))

    assert client.post("/api/v1/render/missing", json={"version": "original"}).status_code == 404
    assert client.post("/api/v1/render/proj-no-script", json={"version": "original"}).status_code == 422
    assert client.get("/api/v1/render/job-missing").status_code == 404


def test_default_render_route_dispatches_celery_task(tmp_path: Path, monkeypatch) -> None:
    from routes import render as render_routes

    repository = seeded_repository(tmp_path)
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    calls: list[tuple[str, str, str, str, str | None]] = []

    monkeypatch.setattr(
        render_routes,
        "dispatch_render_task",
        lambda job_id, project_id, version, resolution, script_version=None: calls.append(
            (job_id, project_id, version, resolution, script_version)
        ),
    )
    app = FastAPI()
    app.include_router(build_render_router(repository, settings))
    client = TestClient(app)

    response = client.post("/api/v1/render/proj-1", json={"version": "original", "resolution": "720p"})

    assert response.status_code == 200
    assert calls and calls[0][1:] == ("proj-1", "original", "720p", None)


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


def test_legacy_svg_packaging_asset_is_regenerated_as_visible_png(tmp_path: Path, monkeypatch) -> None:
    from services import compositor as compositor_module
    from services.compositor import Compositor

    repository = seeded_repository(tmp_path)
    svg_path = tmp_path / "uploads" / "proj-1" / "assets" / "gap.svg"
    svg_path.parent.mkdir(parents=True)
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"></svg>', encoding="utf-8")
    asset = repository.create_asset(
        project_id="proj-1",
        name="gap.svg",
        asset_type="image",
        file_path=str(svg_path),
        tag="packaging",
        analysis={"description": "Packaging fill", "ocr_text": "Limited offer"},
        origin="packaging",
    )
    script = final_script_payload()
    script["segments"][0]["asset_id"] = asset["id"]
    repository.save_project_script("proj-1", script)
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> None:
        commands.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"fake mp4")

    monkeypatch.setattr(compositor_module, "_run", fake_run)
    job = repository.create_render_job(project_id="proj-1", version="original")

    Compositor(repository, settings).render(job_id=job["id"], project_id="proj-1", version="original", resolution="720p")

    loaded = repository.get_render_job(job["id"])
    assert loaded is not None
    assert loaded["status"] == "completed"
    assert any("regenerated legacy packaging asset" in warning for warning in loaded["warnings"])
    assert commands[0][1:4] == ["-y", "-loop", "1"]
    assert any(str(argument).endswith(".png") for argument in commands[0])


def test_unbound_packaging_segment_renders_visible_card(tmp_path: Path, monkeypatch) -> None:
    from services import compositor as compositor_module
    from services.compositor import Compositor

    repository = seeded_repository(tmp_path)
    script = final_script_payload()
    script["segments"][0]["source"] = "packaging"
    repository.save_project_script("proj-1", script)
    settings = Settings(db_path=tmp_path / "structforge.db", output_dir=tmp_path / "outputs")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> None:
        commands.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"fake mp4")

    monkeypatch.setattr(compositor_module, "_run", fake_run)
    job = repository.create_render_job(project_id="proj-1", version="original")

    Compositor(repository, settings).render(job_id=job["id"], project_id="proj-1", version="original", resolution="720p")

    loaded = repository.get_render_job(job["id"])
    assert loaded is not None
    assert any("render-time packaging card" in warning for warning in loaded["warnings"])
    assert commands[0][1:4] == ["-y", "-loop", "1"]
    assert any(str(argument).endswith(".png") for argument in commands[0])


def test_render_commands_include_audio_and_conversion_extends_cta_duration(tmp_path: Path) -> None:
    from services.compositor import _version_filters, build_image_command, build_placeholder_command

    placeholder = build_placeholder_command(
        ffmpeg_path="ffmpeg",
        output_path=tmp_path / "placeholder.mp4",
        ass_path=tmp_path / "cta.ass",
        duration=5,
        width=720,
        height=1280,
        version="strong_conversion",
        segment_type="cta",
    )
    image = build_image_command(
        ffmpeg_path="ffmpeg",
        input_path=tmp_path / "card.png",
        output_path=tmp_path / "image.mp4",
        ass_path=tmp_path / "hook.ass",
        duration=3,
        width=720,
        height=1280,
        version="original",
        segment_type="hook",
    )

    assert "-an" not in placeholder and "-c:a" in placeholder
    assert "-an" not in image and "-c:a" in image
    assert "7.000" in placeholder
    assert "tpad=stop_mode=clone:stop_duration=2" in _version_filters(
        720, 1280, tmp_path / "cta.ass", "strong_conversion", "cta"
    )


def test_real_ffmpeg_renders_visible_packaging_video_when_available(tmp_path: Path) -> None:
    from services.compositor import Compositor

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        pytest.skip("ffmpeg/ffprobe not installed; render integration test skipped")

    repository = seeded_repository(tmp_path)
    script = final_script_payload()
    for segment in script["segments"]:
        segment["source"] = "packaging"
    repository.save_project_script("proj-1", script)
    settings = Settings(
        db_path=tmp_path / "structforge.db",
        output_dir=tmp_path / "outputs",
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
    )
    job = repository.create_render_job(project_id="proj-1", version="strong_conversion")

    Compositor(repository, settings).render(
        job_id=job["id"],
        project_id="proj-1",
        version="strong_conversion",
        resolution="720p",
    )

    loaded = repository.get_render_job(job["id"])
    output_path = tmp_path / "outputs" / "proj-1" / "strong_conversion.mp4"
    assert loaded is not None
    assert loaded["status"] == "completed", loaded.get("error")
    assert output_path.exists()
    probe = subprocess.run(
        [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(output_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert float(probe.stdout.strip()) >= 9.5


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
