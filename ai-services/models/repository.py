from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine

from models.schemas import JobStatus, VideoStructure


metadata = MetaData()


analysis_jobs = Table(
    "analysis_jobs",
    metadata,
    Column("job_id", String, primary_key=True),
    Column("project_id", String, nullable=True),
    Column("status", String, nullable=False),
    Column("progress", Integer, nullable=False),
    Column("stage", String, nullable=False),
    Column("source_path", Text, nullable=False),
    Column("result_json", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("status", String, nullable=False),
    Column("analysis_result_json", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_value(status: JobStatus | str) -> str:
    return status.value if isinstance(status, JobStatus) else status


class SQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(f"sqlite:///{self.db_path}", future=True)

    def initialize(self) -> None:
        metadata.create_all(self.engine)

    def create_job(self, job_id: str, source_path: str, project_id: str | None = None) -> None:
        now = _utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                analysis_jobs.insert().values(
                    job_id=job_id,
                    project_id=project_id,
                    status=JobStatus.PENDING.value,
                    progress=0,
                    stage="Queued",
                    source_path=source_path,
                    result_json=None,
                    error=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | str | None = None,
        progress: int | None = None,
        stage: str | None = None,
        result: VideoStructure | dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"updated_at": _utc_now()}
        if status is not None:
            values["status"] = _status_value(status)
        if progress is not None:
            values["progress"] = progress
        if stage is not None:
            values["stage"] = stage
        if result is not None:
            if isinstance(result, VideoStructure):
                result_payload = result.model_dump(mode="json")
            else:
                result_payload = VideoStructure.model_validate(result).model_dump(mode="json")
            values["result_json"] = json.dumps(result_payload, ensure_ascii=False)
        if error is not None:
            values["error"] = error

        with self.engine.begin() as connection:
            connection.execute(
                analysis_jobs.update().where(analysis_jobs.c.job_id == job_id).values(**values)
            )

    def complete_job(self, job_id: str, result: VideoStructure | dict[str, Any]) -> None:
        structure = VideoStructure.model_validate(result)
        self.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            stage="Analysis completed",
            result=structure,
        )
        job = self.get_job(job_id)
        if job and job.get("project_id"):
            self.upsert_project(
                project_id=job["project_id"],
                status="completed",
                analysis_result=structure,
            )

    def fail_job(self, job_id: str, error: str, stage: str = "Analysis failed") -> None:
        self.update_job(job_id, status=JobStatus.FAILED, progress=100, stage=stage, error=error)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(analysis_jobs).where(analysis_jobs.c.job_id == job_id)
            ).first()
        if row is None:
            return None
        data = dict(row._mapping)
        data["result"] = json.loads(data["result_json"]) if data.get("result_json") else None
        return data

    def upsert_project(
        self,
        project_id: str,
        name: str | None = None,
        status: str = "analyzing",
        analysis_result: VideoStructure | dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        result_json = None
        if analysis_result is not None:
            structure = VideoStructure.model_validate(analysis_result)
            result_json = json.dumps(structure.model_dump(mode="json"), ensure_ascii=False)

        with self.engine.begin() as connection:
            existing = connection.execute(
                select(projects).where(projects.c.id == project_id)
            ).first()
            if existing:
                values: dict[str, Any] = {"status": status, "updated_at": now}
                if name is not None:
                    values["name"] = name
                if result_json is not None:
                    values["analysis_result_json"] = result_json
                connection.execute(projects.update().where(projects.c.id == project_id).values(**values))
            else:
                connection.execute(
                    projects.insert().values(
                        id=project_id,
                        name=name or project_id,
                        status=status,
                        analysis_result_json=result_json,
                        created_at=now,
                        updated_at=now,
                    )
                )

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(select(projects).where(projects.c.id == project_id)).first()
        if row is None:
            return None
        data = dict(row._mapping)
        data["analysis_result"] = (
            json.loads(data["analysis_result_json"])
            if data.get("analysis_result_json")
            else None
        )
        return data
