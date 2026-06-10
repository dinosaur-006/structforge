from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if ffmpeg is None or ffprobe is None:
    pytest.skip("ffmpeg/ffprobe not installed; media integration test skipped", allow_module_level=True)

from config import Settings
import main as main_module
from main import create_app
from models.repository import SQLiteRepository
from services.pipeline import AnalysisPipeline
from tasks.analyze import analyze_video_task


def test_pipeline_generates_frontend_structure_from_short_video(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=320x568:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=3",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
        str(video_path),
    ],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

    settings = Settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        db_path=tmp_path / "structforge.db",
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        doubao_llm_endpoint=None,
        doubao_llm_api_key=None,
    )
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()
    repository.create_job("job-1", str(video_path))

    structure = AnalysisPipeline(settings=settings, repository=repository).run("job-1", video_path)

    assert len(structure.script) >= 3
    assert len(structure.rhythm) >= 5
    assert set(structure.model_dump(mode="json")) == {"meta", "script", "rhythm", "packaging", "health"}


def test_project_analyze_structure_api_integration(tmp_path: Path, monkeypatch) -> None:
    video_path = _make_test_video(tmp_path)
    monkeypatch.setenv("STRUCTFORGE_DB_PATH", str(tmp_path / "structforge.db"))
    monkeypatch.setenv("STRUCTFORGE_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("STRUCTFORGE_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("STRUCTFORGE_FFMPEG_PATH", ffmpeg)
    monkeypatch.setenv("STRUCTFORGE_FFPROBE_PATH", ffprobe)
    monkeypatch.delenv("STRUCTFORGE_DOUBAO_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("STRUCTFORGE_DOUBAO_LLM_API_KEY", raising=False)
    monkeypatch.setenv("STRUCTFORGE_DOUBAO_LLM_ENDPOINT", "")
    monkeypatch.setenv("STRUCTFORGE_DOUBAO_LLM_API_KEY", "")
    monkeypatch.setattr(
        main_module,
        "dispatch_analyze_task",
        lambda job_id, source_path: analyze_video_task(job_id, source_path),
    )
    client = TestClient(create_app())

    project = client.post("/api/v1/projects", json={"name": "API integration"}).json()
    with video_path.open("rb") as handle:
        upload = client.post(
            "/api/v1/analyze",
            data={"project_id": project["id"]},
            files={"video": ("sample.mp4", handle, "video/mp4")},
        )
    status = client.get(f"/api/v1/analyze/{upload.json()['job_id']}")
    refreshed_project = client.get(f"/api/v1/projects/{project['id']}")
    structure = client.get(f"/api/v1/structure/{project['id']}")
    assets = client.get(f"/api/v1/assets/{project['id']}")
    updated = client.put(
        f"/api/v1/structure/{project['id']}/segment/seg-1",
        json={"copy": "Integration edit"},
    )

    assert upload.status_code == 200
    assert status.json()["status"] == "completed"
    assert refreshed_project.json()["status"] == "editing"
    assert len(structure.json()["script"]) >= 3
    source_asset = next(asset for asset in assets.json() if asset["type"] == "video")
    assert all(segment["assetId"] == source_asset["id"] for segment in structure.json()["script"])
    assert updated.json()["script"][0]["copy"] == "Integration edit"


def _make_test_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "api_sample.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=320x568:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=3",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return video_path
