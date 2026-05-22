from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from models.repository import SQLiteRepository
from services.projects import ProjectNotFoundError, ProjectService
from services.structure_editor import (
    ReorderValidationError,
    SegmentNotFoundError,
    StructureEditor,
    StructureNotFoundError,
)
from tests.test_schemas import valid_video_structure_payload


def test_repository_migrates_existing_projects_table_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "structforge.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "analysis_result_json TEXT, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
        )

    repository = SQLiteRepository(db_path)
    repository.initialize()
    repository.initialize()

    with repository.engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(projects)"))}

    assert {"description", "current_structure", "undo_stack", "redo_stack"}.issubset(columns)


def test_project_service_creates_lists_updates_and_deletes_project(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    service = ProjectService(repository)

    project = service.create_project(name="Launch A", description="First")
    service.create_project(name="Launch B", description="Second")
    updated = service.update_project(project["id"], name="Launch A revised")
    projects = service.list_projects()

    assert updated["name"] == "Launch A revised"
    assert projects[0]["updatedAt"] >= projects[1]["updatedAt"]
    assert set(projects[0]) == {"id", "name", "description", "status", "updatedAt"}

    service.delete_project(project["id"])
    with pytest.raises(ProjectNotFoundError):
        service.get_project(project["id"])


def test_complete_job_initializes_editable_project_structure(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-1", name="Headphones", status="analyzing")
    repository.create_job("job-1", "data/uploads/job-1_source.mp4", project_id="proj-1")

    repository.complete_job("job-1", valid_video_structure_payload())
    project = repository.get_project("proj-1")

    assert project is not None
    assert project["status"] == "editing"
    assert project["analysis_result"]["health"]["overall"] == 72
    assert project["current_structure"]["health"]["overall"] == 72
    assert project["undo_stack"] == []
    assert project["redo_stack"] == []


def test_structure_editor_lazily_initializes_from_analysis_result(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        analysis_result=valid_video_structure_payload(),
        current_structure=None,
    )

    structure = StructureEditor(repository).get_structure("proj-1")
    project = repository.get_project("proj-1")

    assert structure.meta.duration == 35.0
    assert project is not None
    assert project["current_structure"]["meta"]["duration"] == 35.0


def test_structure_editor_mutates_segments_and_validates_reorder(tmp_path: Path) -> None:
    editor = _editor_with_structure(tmp_path)

    created = editor.add_segment(
        "proj-1",
        {
            "type": "proof",
            "label": "Extra proof",
            "start": 12,
            "end": 16,
            "duration": 4,
            "goal": "prove",
            "copy": "More proof",
            "visual": "Bench demo",
        },
    )
    new_id = created.script[-1].id
    updated = editor.update_segment("proj-1", new_id, {"copy": "Updated proof", "healthScore": 77})
    deleted = editor.delete_segment("proj-1", "seg-2")
    order = [segment.id for segment in reversed(deleted.script)]
    reordered = editor.reorder_segments("proj-1", order)

    assert len(created.script) == 4
    assert updated.script[-1].copy_text == "Updated proof"
    assert len(deleted.script) == 3
    assert [segment.id for segment in reordered.script] == order

    with pytest.raises(SegmentNotFoundError):
        editor.delete_segment("proj-1", "missing")
    with pytest.raises(ReorderValidationError):
        editor.reorder_segments("proj-1", order[:-1])
    with pytest.raises(ReorderValidationError):
        editor.reorder_segments("proj-1", order + ["extra"])
    with pytest.raises(ReorderValidationError):
        editor.reorder_segments("proj-1", [order[0], order[0], *order[1:-1]])


def test_structure_editor_undo_redo_and_reset(tmp_path: Path) -> None:
    editor = _editor_with_structure(tmp_path)

    for index in range(1, 6):
        editor.update_segment("proj-1", "seg-1", {"copy": f"Edit {index}"})

    undo_1 = editor.undo("proj-1")
    undo_2 = editor.undo("proj-1")
    undo_3 = editor.undo("proj-1")
    redo_1 = editor.redo("proj-1")
    redo_2 = editor.redo("proj-1")

    assert undo_1.available is True
    assert undo_3.structure.script[0].copy_text == "Edit 2"
    assert redo_2.structure.script[0].copy_text == "Edit 4"

    editor.update_segment("proj-1", "seg-1", {"copy": "Fresh edit"})
    project_after_fresh_edit = editor.repository.get_project("proj-1")
    assert project_after_fresh_edit is not None
    assert project_after_fresh_edit["redo_stack"] == []

    reset = editor.reset("proj-1")
    project_after_reset = editor.repository.get_project("proj-1")
    assert reset.script[0].copy_text == "A sharper opener"
    assert project_after_reset is not None
    assert project_after_reset["undo_stack"] == []
    assert project_after_reset["redo_stack"] == []


def test_empty_undo_redo_returns_current_structure(tmp_path: Path) -> None:
    editor = _editor_with_structure(tmp_path)

    undo = editor.undo("proj-1")
    redo = editor.redo("proj-1")

    assert undo.available is False
    assert undo.structure.meta.duration == 35.0
    assert redo.available is False
    assert redo.structure.meta.duration == 35.0


def test_structure_editor_raises_for_missing_project(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()

    with pytest.raises(StructureNotFoundError):
        StructureEditor(repository).get_structure("missing")


def _editor_with_structure(tmp_path: Path) -> StructureEditor:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        status="editing",
        analysis_result=valid_video_structure_payload(),
        current_structure=valid_video_structure_payload(),
    )
    return StructureEditor(repository)
