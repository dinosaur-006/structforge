from __future__ import annotations

from models.repository import SQLiteRepository


class ProjectNotFoundError(LookupError):
    pass


class ProjectService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def create_project(self, *, name: str, description: str = "") -> dict:
        return self._to_project_out(self.repository.create_project(name=name, description=description))

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
    ) -> dict:
        project = self.repository.update_project(
            project_id,
            name=name,
            description=description,
        )
        if project is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return self._to_project_out(project)

    def delete_project(self, project_id: str) -> None:
        if not self.repository.delete_project(project_id):
            raise ProjectNotFoundError(f"Project not found: {project_id}")

    def _to_project_out(self, project: dict) -> dict:
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project.get("description") or "",
            "status": project["status"],
            "updatedAt": project["updated_at"],
        }
