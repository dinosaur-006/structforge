from __future__ import annotations

from pathlib import Path

from models.repository import SQLiteRepository
from models.schemas import JobStatus
from tests.test_schemas import valid_video_structure_payload


def test_repository_creates_and_updates_analysis_job(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()

    repository.create_job(
        job_id="job-1",
        source_path="data/uploads/job-1_source.mp4",
        project_id="proj-1",
    )
    repository.update_job(
        "job-1",
        status=JobStatus.PROCESSING,
        progress=42,
        stage="Extracting metadata",
    )
    job = repository.get_job("job-1")

    assert job is not None
    assert job["project_id"] == "proj-1"
    assert job["status"] == "processing"
    assert job["progress"] == 42
    assert job["stage"] == "Extracting metadata"


def test_repository_persists_result_to_job_and_project(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-1", name="Headphone launch")
    repository.create_job(
        job_id="job-1",
        source_path="data/uploads/job-1_source.mp4",
        project_id="proj-1",
    )

    repository.complete_job("job-1", valid_video_structure_payload())
    job = repository.get_job("job-1")
    project = repository.get_project("proj-1")

    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["meta"]["duration"] == 35.0
    assert project is not None
    assert project["analysis_result"]["health"]["overall"] == 72
