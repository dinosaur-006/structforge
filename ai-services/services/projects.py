from __future__ import annotations

import shutil
from pathlib import Path

from models.repository import SQLiteRepository


class ProjectNotFoundError(LookupError):
    pass


class ProjectService:
    def __init__(
        self,
        repository: SQLiteRepository,
        upload_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.upload_dir = upload_dir
        self.output_dir = output_dir

    def create_project(self, *, name: str, description: str = "", brief: dict | None = None) -> dict:
        return self._to_project_out(self.repository.create_project(name=name, description=description, brief=brief))

    def list_projects(self) -> list[dict]:
        return [self._to_project_out(project) for project in self.repository.list_projects()]

    def get_project(self, project_id: str) -> dict:
        project = self.repository.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return self._to_project_out(project)

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        brief: dict | None = None,
    ) -> dict:
        project = self.repository.update_project(
            project_id,
            name=name,
            description=description,
            brief=brief,
        )
        if project is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return self._to_project_out(project)

    def delete_project(self, project_id: str) -> None:
        if not self.repository.delete_project(project_id):
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        if self.upload_dir is not None:
            shutil.rmtree(self.upload_dir / project_id, ignore_errors=True)
        if self.output_dir is not None:
            shutil.rmtree(self.output_dir / project_id, ignore_errors=True)

    def _to_project_out(self, project: dict) -> dict:
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project.get("description") or "",
            "brief": project.get("brief") or {},
            "status": project["status"],
            "updatedAt": project["updated_at"],
        }
