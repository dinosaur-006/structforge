from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from models.repository import SQLiteRepository
from models.schemas import ScriptSegment, VideoStructure


class StructureNotFoundError(LookupError):
    pass


class SegmentNotFoundError(LookupError):
    pass


class ReorderValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StructureActionResult:
    action: str
    available: bool
    structure: VideoStructure


class StructureEditor:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def get_structure(self, project_id: str) -> VideoStructure:
        project = self._get_project(project_id)
        current = project.get("current_structure")
        if current is not None:
            return VideoStructure.model_validate(current)

        analysis_result = project.get("analysis_result")
        if analysis_result is None:
            raise StructureNotFoundError(f"Project has no structure: {project_id}")

        structure = VideoStructure.model_validate(analysis_result)
        self.repository.save_project_structure_state(
            project_id,
            current_structure=structure,
            undo_stack=project.get("undo_stack") or [],
            redo_stack=project.get("redo_stack") or [],
        )
        return structure

    def replace_structure(self, project_id: str, payload: dict[str, Any]) -> VideoStructure:
        new_structure = VideoStructure.model_validate(payload)
        return self._write_structure(project_id, new_structure)

    def add_segment(self, project_id: str, payload: dict[str, Any]) -> VideoStructure:
        current = self.get_structure(project_id)
        segment_payload = {
            "id": payload.get("id") or f"seg-{uuid4()}",
            "locked": False,
            "healthScore": 50,
            **payload,
        }
        segment_payload["id"] = segment_payload.get("id") or f"seg-{uuid4()}"
        segment = ScriptSegment.model_validate(segment_payload)
        updated = current.model_copy(update={"script": [*current.script, segment]})
        return self._write_structure(project_id, updated)

    def update_segment(self, project_id: str, segment_id: str, payload: dict[str, Any]) -> VideoStructure:
        current = self.get_structure(project_id)
        updated_segments: list[ScriptSegment] = []
        found = False
        for segment in current.script:
            if segment.id != segment_id:
                updated_segments.append(segment)
                continue
            merged = segment.model_dump(mode="json", by_alias=True)
            merged.update(payload)
            merged["id"] = segment_id
            updated_segments.append(ScriptSegment.model_validate(merged))
            found = True
        if not found:
            raise SegmentNotFoundError(f"Segment not found: {segment_id}")
        updated = current.model_copy(update={"script": updated_segments})
        return self._write_structure(project_id, updated)

    def delete_segment(self, project_id: str, segment_id: str) -> VideoStructure:
        current = self.get_structure(project_id)
        updated_segments = [segment for segment in current.script if segment.id != segment_id]
        if len(updated_segments) == len(current.script):
            raise SegmentNotFoundError(f"Segment not found: {segment_id}")
        updated = current.model_copy(update={"script": updated_segments})
        return self._write_structure(project_id, updated)

    def reorder_segments(self, project_id: str, order: list[str]) -> VideoStructure:
        current = self.get_structure(project_id)
        current_ids = [segment.id for segment in current.script]
        if len(order) != len(set(order)):
            raise ReorderValidationError("Order must not contain duplicate segment IDs")
        if set(order) != set(current_ids):
            raise ReorderValidationError("Order must contain exactly the current segment IDs")

        by_id = {segment.id: segment for segment in current.script}
        updated = current.model_copy(update={"script": [by_id[segment_id] for segment_id in order]})
        return self._write_structure(project_id, updated)

    def undo(self, project_id: str) -> StructureActionResult:
        project = self._get_project(project_id)
        current = self.get_structure(project_id)
        undo_stack = project.get("undo_stack") or []
        redo_stack = project.get("redo_stack") or []
        if not undo_stack:
            return StructureActionResult(action="undo", available=False, structure=current)

        previous = VideoStructure.model_validate(undo_stack[-1])
        new_undo = undo_stack[:-1]
        new_redo = [*redo_stack, current.model_dump(mode="json", by_alias=True)]
        self.repository.save_project_structure_state(
            project_id,
            current_structure=previous,
            undo_stack=new_undo,
            redo_stack=new_redo,
        )
        return StructureActionResult(action="undo", available=True, structure=previous)

    def redo(self, project_id: str) -> StructureActionResult:
        project = self._get_project(project_id)
        current = self.get_structure(project_id)
        undo_stack = project.get("undo_stack") or []
        redo_stack = project.get("redo_stack") or []
        if not redo_stack:
            return StructureActionResult(action="redo", available=False, structure=current)

        next_structure = VideoStructure.model_validate(redo_stack[-1])
        new_redo = redo_stack[:-1]
        new_undo = self._capped_stack([*undo_stack, current.model_dump(mode="json", by_alias=True)])
        self.repository.save_project_structure_state(
            project_id,
            current_structure=next_structure,
            undo_stack=new_undo,
            redo_stack=new_redo,
        )
        return StructureActionResult(action="redo", available=True, structure=next_structure)

    def reset(self, project_id: str) -> VideoStructure:
        project = self._get_project(project_id)
        analysis_result = project.get("analysis_result")
        if analysis_result is None:
            raise StructureNotFoundError(f"Project has no analysis result: {project_id}")
        structure = VideoStructure.model_validate(analysis_result)
        self.repository.clear_project_history_and_reset_structure(project_id, structure)
        return structure

    def _write_structure(self, project_id: str, new_structure: VideoStructure) -> VideoStructure:
        project = self._get_project(project_id)
        current = self.get_structure(project_id)
        undo_stack = project.get("undo_stack") or []
        new_undo = self._capped_stack([*undo_stack, current.model_dump(mode="json", by_alias=True)])
        saved = self.repository.save_project_structure_state(
            project_id,
            current_structure=new_structure,
            undo_stack=new_undo,
            redo_stack=[],
        )
        if saved is None:
            raise StructureNotFoundError(f"Project not found: {project_id}")
        return new_structure

    def _get_project(self, project_id: str) -> dict:
        project = self.repository.get_project(project_id)
        if project is None:
            raise StructureNotFoundError(f"Project not found: {project_id}")
        return project

    def _capped_stack(self, stack: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return stack[-20:]
