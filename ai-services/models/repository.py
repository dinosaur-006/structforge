from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, select, text
from sqlalchemy.engine import Engine

from models.schemas import FinalScript, JobStatus, ResultEvaluation, VideoStructure


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
    Column("description", Text, nullable=False, default=""),
    Column("brief_json", Text, nullable=True),
    Column("status", String, nullable=False),
    Column("analysis_result_json", Text, nullable=True),
    Column("current_structure", Text, nullable=True),
    Column("undo_stack", Text, nullable=True),
    Column("redo_stack", Text, nullable=True),
    Column("script_json", Text, nullable=True),
    Column("reference_job_id", String, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


assets = Table(
    "assets",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, nullable=False),
    Column("name", String, nullable=False),
    Column("type", String, nullable=False),
    Column("file_path", Text, nullable=True),
    Column("tag", String, nullable=False),
    Column("match_status", String, nullable=False),
    Column("match_score", Float, nullable=False),
    Column("analysis_json", Text, nullable=True),
    Column("origin", String, nullable=False, default="uploaded"),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


render_jobs = Table(
    "render_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, nullable=False),
    Column("version", String, nullable=False),
    Column("status", String, nullable=False),
    Column("progress", Float, nullable=False),
    Column("output_path", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("warnings_json", Text, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

script_versions = Table(
    "script_versions",
    metadata,
    Column("project_id", String, primary_key=True),
    Column("version", String, primary_key=True),
    Column("script_json", Text, nullable=False),
    Column("evaluation_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_value(status: JobStatus | str) -> str:
    return status.value if isinstance(status, JobStatus) else status


_UNSET = object()


def _dump_structure(structure: VideoStructure | dict[str, Any] | None) -> str | None:
    if structure is None:
        return None
    payload = VideoStructure.model_validate(structure).model_dump(mode="json", by_alias=True)
    return json.dumps(payload, ensure_ascii=False)


def _dump_stack(stack: list[VideoStructure | dict[str, Any]] | None) -> str:
    payload = [
        VideoStructure.model_validate(item).model_dump(mode="json", by_alias=True)
        for item in (stack or [])
    ]
    return json.dumps(payload, ensure_ascii=False)


def _dump_script(script: FinalScript | dict[str, Any] | None) -> str | None:
    if script is None:
        return None
    payload = FinalScript.model_validate(script).model_dump(mode="json", by_alias=True)
    return json.dumps(payload, ensure_ascii=False)


def _load_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


class SQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(f"sqlite:///{self.db_path}", future=True)

    def initialize(self) -> None:
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))
        self._migrate_projects_table()
        self._migrate_assets_table()
        self._migrate_render_jobs_table()

    def _migrate_projects_table(self) -> None:
        required_columns = {
            "description": "TEXT NOT NULL DEFAULT ''",
            "brief_json": "TEXT",
            "current_structure": "TEXT",
            "undo_stack": "TEXT",
            "redo_stack": "TEXT",
            "script_json": "TEXT",
            "reference_job_id": "TEXT",
        }
        with self.engine.begin() as connection:
            existing_columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(projects)"))
            }
            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE projects ADD COLUMN {column_name} {column_definition}")
                    )

    def _migrate_assets_table(self) -> None:
        required_columns = {
            "id": "TEXT PRIMARY KEY",
            "project_id": "TEXT NOT NULL",
            "name": "TEXT NOT NULL DEFAULT ''",
            "type": "TEXT NOT NULL DEFAULT 'image'",
            "file_path": "TEXT",
            "tag": "TEXT NOT NULL DEFAULT ''",
            "match_status": "TEXT NOT NULL DEFAULT 'unmatched'",
            "match_score": "REAL NOT NULL DEFAULT 0",
            "analysis_json": "TEXT",
            "origin": "TEXT NOT NULL DEFAULT 'uploaded'",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }
        with self.engine.begin() as connection:
            existing_columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))
            }
            if not existing_columns:
                metadata.create_all(connection)
                return
            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE assets ADD COLUMN {column_name} {column_definition}")
                    )

    def _migrate_render_jobs_table(self) -> None:
        required_columns = {
            "id": "TEXT PRIMARY KEY",
            "project_id": "TEXT NOT NULL",
            "version": "TEXT NOT NULL",
            "status": "TEXT NOT NULL DEFAULT 'pending'",
            "progress": "REAL NOT NULL DEFAULT 0",
            "output_path": "TEXT",
            "error": "TEXT",
            "warnings_json": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }
        with self.engine.begin() as connection:
            existing_columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(render_jobs)"))
            }
            if not existing_columns:
                metadata.create_all(connection)
                return
            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE render_jobs ADD COLUMN {column_name} {column_definition}")
                    )

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
                result_payload = result.model_dump(mode="json", by_alias=True)
            else:
                result_payload = VideoStructure.model_validate(result).model_dump(mode="json", by_alias=True)
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
            project = self.get_project(job["project_id"])
            if not project or not project.get("reference_job_id"):
                self.upsert_project(
                    project_id=job["project_id"],
                    status="editing",
                    analysis_result=structure,
                    current_structure=structure,
                    undo_stack=[],
                    redo_stack=[],
                    reference_job_id=job_id,
                )
            else:
                self.upsert_project(project_id=job["project_id"], status="editing")

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

    def list_project_jobs(self, project_id: str) -> list[dict[str, Any]]:
        project = self.get_project(project_id)
        if project is None:
            return []
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(analysis_jobs)
                .where(analysis_jobs.c.project_id == project_id)
                .order_by(analysis_jobs.c.created_at.asc())
            ).all()
        return [
            {
                **dict(row._mapping),
                "result": _load_json(row._mapping["result_json"], None),
                "isReference": row._mapping["job_id"] == project.get("reference_job_id"),
            }
            for row in rows
        ]

    def select_reference_job(
        self,
        project_id: str,
        job_id: str,
        structure_override: VideoStructure | dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job or job.get("project_id") != project_id or not job.get("result"):
            return None
        selected_structure = structure_override or job["result"]
        with self.engine.begin() as connection:
            result = connection.execute(
                projects.update()
                .where(projects.c.id == project_id)
                .values(
                    analysis_result_json=_dump_structure(selected_structure),
                    current_structure=_dump_structure(selected_structure),
                    undo_stack="[]",
                    redo_stack="[]",
                    script_json=None,
                    reference_job_id=job_id,
                    status="editing",
                    updated_at=_utc_now(),
                )
            )
            connection.execute(script_versions.delete().where(script_versions.c.project_id == project_id))
        if result.rowcount == 0:
            return None
        return {**job, "result": VideoStructure.model_validate(selected_structure).model_dump(mode="json", by_alias=True), "isReference": True}

    def upsert_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        brief: dict[str, Any] | None | object = _UNSET,
        status: str = "analyzing",
        analysis_result: VideoStructure | dict[str, Any] | None = None,
        current_structure: VideoStructure | dict[str, Any] | None | object = _UNSET,
        undo_stack: list[VideoStructure | dict[str, Any]] | None | object = _UNSET,
        redo_stack: list[VideoStructure | dict[str, Any]] | None | object = _UNSET,
        reference_job_id: str | None | object = _UNSET,
    ) -> None:
        now = _utc_now()
        result_json = _dump_structure(analysis_result) if analysis_result is not None else None
        current_json = (
            _dump_structure(current_structure) if current_structure is not _UNSET else _UNSET
        )
        undo_json = _dump_stack(undo_stack) if undo_stack is not _UNSET else _UNSET
        redo_json = _dump_stack(redo_stack) if redo_stack is not _UNSET else _UNSET
        brief_json = json.dumps(brief, ensure_ascii=False) if brief is not _UNSET and brief is not None else (None if brief is None else _UNSET)

        with self.engine.begin() as connection:
            existing = connection.execute(
                select(projects).where(projects.c.id == project_id)
            ).first()
            if existing:
                values: dict[str, Any] = {"status": status, "updated_at": now}
                if name is not None:
                    values["name"] = name
                if description is not None:
                    values["description"] = description
                if brief_json is not _UNSET:
                    values["brief_json"] = brief_json
                if result_json is not None:
                    values["analysis_result_json"] = result_json
                if current_json is not _UNSET:
                    values["current_structure"] = current_json
                if undo_json is not _UNSET:
                    values["undo_stack"] = undo_json
                if redo_json is not _UNSET:
                    values["redo_stack"] = redo_json
                if reference_job_id is not _UNSET:
                    values["reference_job_id"] = reference_job_id
                connection.execute(projects.update().where(projects.c.id == project_id).values(**values))
            else:
                connection.execute(
                    projects.insert().values(
                        id=project_id,
                        name=name or project_id,
                        description=description or "",
                        brief_json="{}" if brief_json is _UNSET else brief_json,
                        status=status,
                    analysis_result_json=result_json,
                    current_structure=None if current_json is _UNSET else current_json,
                    undo_stack="[]" if undo_json is _UNSET else undo_json,
                    redo_stack="[]" if redo_json is _UNSET else redo_json,
                    script_json=None,
                    reference_job_id=None if reference_job_id is _UNSET else reference_job_id,
                    created_at=now,
                    updated_at=now,
                )
                )

    def create_project(self, name: str, description: str = "", brief: dict[str, Any] | None = None) -> dict[str, Any]:
        project_id = str(uuid4())
        now = _utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                projects.insert().values(
                    id=project_id,
                    name=name,
                    description=description,
                    brief_json=json.dumps(brief or {}, ensure_ascii=False),
                    status="draft",
                    analysis_result_json=None,
                    current_structure=None,
                    undo_stack="[]",
                    redo_stack="[]",
                    script_json=None,
                    reference_job_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        project = self.get_project(project_id)
        if project is None:
            raise RuntimeError("Failed to create project")
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = connection.execute(select(projects).order_by(projects.c.updated_at.desc())).all()
        return [self._project_row_to_dict(row._mapping) for row in rows]

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        brief: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        values: dict[str, Any] = {"updated_at": _utc_now()}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if brief is not None:
            values["brief_json"] = json.dumps(brief, ensure_ascii=False)
        with self.engine.begin() as connection:
            result = connection.execute(
                projects.update().where(projects.c.id == project_id).values(**values)
            )
        if result.rowcount == 0:
            return None
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        with self.engine.begin() as connection:
            connection.execute(assets.delete().where(assets.c.project_id == project_id))
            connection.execute(render_jobs.delete().where(render_jobs.c.project_id == project_id))
            connection.execute(script_versions.delete().where(script_versions.c.project_id == project_id))
            connection.execute(analysis_jobs.delete().where(analysis_jobs.c.project_id == project_id))
            result = connection.execute(projects.delete().where(projects.c.id == project_id))
        return result.rowcount > 0

    def create_render_job(self, *, project_id: str, version: str) -> dict[str, Any]:
        job_id = str(uuid4())
        now = _utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                render_jobs.insert().values(
                    id=job_id,
                    project_id=project_id,
                    version=version,
                    status="pending",
                    progress=0.0,
                    output_path=None,
                    error=None,
                    warnings_json="[]",
                    created_at=now,
                    updated_at=now,
                )
            )
        job = self.get_render_job(job_id)
        if job is None:
            raise RuntimeError("Failed to create render job")
        return job

    def update_render_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        output_path: str | None = None,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        values: dict[str, Any] = {"updated_at": _utc_now()}
        if status is not None:
            values["status"] = status
        if progress is not None:
            values["progress"] = max(0.0, min(float(progress), 100.0))
        if output_path is not None:
            values["output_path"] = output_path
        if error is not None:
            values["error"] = error
        if warnings is not None:
            values["warnings_json"] = json.dumps(warnings, ensure_ascii=False)
        with self.engine.begin() as connection:
            connection.execute(render_jobs.update().where(render_jobs.c.id == job_id).values(**values))

    def get_render_job(self, job_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(select(render_jobs).where(render_jobs.c.id == job_id)).first()
        if row is None:
            return None
        data = dict(row._mapping)
        data["warnings"] = _load_json(data.get("warnings_json"), [])
        data["progress"] = float(data.get("progress") or 0)
        return data

    def save_project_script(self, project_id: str, script: FinalScript | dict[str, Any]) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            result = connection.execute(
                projects.update()
                .where(projects.c.id == project_id)
                .values(script_json=_dump_script(script), updated_at=_utc_now())
            )
        if result.rowcount == 0:
            return None
        return self.get_project(project_id)

    def get_project_script(self, project_id: str) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        if project is None:
            return None
        return project.get("script")

    def save_script_version(
        self,
        project_id: str,
        script: FinalScript | dict[str, Any],
        evaluation: ResultEvaluation | dict[str, Any],
    ) -> None:
        validated_script = FinalScript.model_validate(script)
        now = _utc_now()
        values = {
            "script_json": _dump_script(validated_script),
            "evaluation_json": json.dumps(
                ResultEvaluation.model_validate(evaluation).model_dump(mode="json"),
                ensure_ascii=False,
            ),
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(script_versions).where(
                    script_versions.c.project_id == project_id,
                    script_versions.c.version == validated_script.version,
                )
            ).first()
            if existing:
                connection.execute(
                    script_versions.update()
                    .where(
                        script_versions.c.project_id == project_id,
                        script_versions.c.version == validated_script.version,
                    )
                    .values(**values)
                )
            else:
                connection.execute(
                    script_versions.insert().values(
                        project_id=project_id,
                        version=validated_script.version,
                        created_at=now,
                        **values,
                    )
                )

    def list_script_versions(self, project_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(script_versions)
                .where(script_versions.c.project_id == project_id)
                .order_by(script_versions.c.updated_at.asc())
            ).all()
        return [
            {
                "version": row._mapping["version"],
                "script": _load_json(row._mapping["script_json"], None),
                "evaluation": _load_json(row._mapping["evaluation_json"], None),
            }
            for row in rows
        ]

    def get_script_version(self, project_id: str, version: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(script_versions).where(
                    script_versions.c.project_id == project_id,
                    script_versions.c.version == version,
                )
            ).first()
        if row is None:
            return None
        return _load_json(row._mapping["script_json"], None)

    def create_asset(
        self,
        *,
        project_id: str,
        name: str,
        asset_type: str,
        file_path: str | None,
        tag: str,
        analysis: dict[str, Any] | None,
        origin: str = "uploaded",
    ) -> dict[str, Any]:
        asset_id = str(uuid4())
        now = _utc_now()
        analysis_json = json.dumps(analysis or {}, ensure_ascii=False)
        with self.engine.begin() as connection:
            connection.execute(
                assets.insert().values(
                    id=asset_id,
                    project_id=project_id,
                    name=name,
                    type=asset_type,
                    file_path=file_path,
                    tag=tag,
                    match_status="unmatched",
                    match_score=0.0,
                    analysis_json=analysis_json,
                    origin=origin,
                    created_at=now,
                    updated_at=now,
                )
            )
        asset = self.get_asset(asset_id)
        if asset is None:
            raise RuntimeError("Failed to create asset")
        return asset

    def list_assets(self, project_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(assets).where(assets.c.project_id == project_id).order_by(assets.c.created_at.desc())
            ).all()
        return [self._asset_row_to_dict(row._mapping) for row in rows]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(select(assets).where(assets.c.id == asset_id)).first()
        if row is None:
            return None
        return self._asset_row_to_dict(row._mapping)

    def update_asset_match(self, asset_id: str, *, score: float, status: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                assets.update()
                .where(assets.c.id == asset_id)
                .values(match_score=score, match_status=status, updated_at=_utc_now())
            )

    def _asset_row_to_dict(self, row: Any) -> dict[str, Any]:
        data = dict(row)
        data["analysis"] = _load_json(data.get("analysis_json"), {})
        data["origin"] = data.get("origin") or "uploaded"
        data["match_score"] = float(data.get("match_score") or 0)
        return data

    def save_project_structure_state(
        self,
        project_id: str,
        *,
        current_structure: VideoStructure | dict[str, Any],
        undo_stack: list[VideoStructure | dict[str, Any]],
        redo_stack: list[VideoStructure | dict[str, Any]],
    ) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            result = connection.execute(
                projects.update()
                .where(projects.c.id == project_id)
                .values(
                    current_structure=_dump_structure(current_structure),
                    undo_stack=_dump_stack(undo_stack),
                    redo_stack=_dump_stack(redo_stack),
                    updated_at=_utc_now(),
                )
            )
        if result.rowcount == 0:
            return None
        return self.get_project(project_id)

    def clear_project_history_and_reset_structure(
        self,
        project_id: str,
        structure: VideoStructure | dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            result = connection.execute(
                projects.update()
                .where(projects.c.id == project_id)
                .values(
                    current_structure=_dump_structure(structure),
                    undo_stack="[]",
                    redo_stack="[]",
                    updated_at=_utc_now(),
                )
            )
        if result.rowcount == 0:
            return None
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(select(projects).where(projects.c.id == project_id)).first()
        if row is None:
            return None
        return self._project_row_to_dict(row._mapping)

    def _project_row_to_dict(self, row: Any) -> dict[str, Any]:
        data = dict(row)
        data["description"] = data.get("description") or ""
        data["analysis_result"] = _load_json(data.get("analysis_result_json"), None)
        data["current_structure"] = _load_json(data.get("current_structure"), None)
        data["undo_stack"] = _load_json(data.get("undo_stack"), [])
        data["redo_stack"] = _load_json(data.get("redo_stack"), [])
        data["script"] = _load_json(data.get("script_json"), None)
        data["reference_job_id"] = data.get("reference_job_id")
        data["brief"] = _load_json(data.get("brief_json"), {})
        return data
