from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from models.repository import SQLiteRepository
from routes.migrate import build_migrate_router
from services.migrator import MigrationError, MigrationInputError, MigratorService
from tests.test_schemas import valid_video_structure_payload


class FakeJsonClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.calls = 0
        self.prompts: list[str] = []

    def complete_json(self, prompt: str) -> object:
        self.prompts.append(prompt)
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return payload


def test_repository_migrates_and_persists_script_json(tmp_path: Path) -> None:
    db_path = tmp_path / "structforge.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "description TEXT NOT NULL DEFAULT '', "
                "status TEXT NOT NULL, "
                "analysis_result_json TEXT, "
                "current_structure TEXT, "
                "undo_stack TEXT, "
                "redo_stack TEXT, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
        )

    repository = SQLiteRepository(db_path)
    repository.initialize()
    repository.initialize()

    with repository.engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(projects)"))}

    assert "script_json" in columns

    repository.upsert_project(
        project_id="proj-1",
        name="Headphones",
        description="AI noise cancelling headphones for office commuters",
        status="editing",
        current_structure=five_segment_structure(),
    )
    script = final_script_payload(version="high_click")
    repository.save_project_script("proj-1", script)

    loaded = repository.get_project_script("proj-1")

    assert loaded is not None
    assert loaded["version"] == "high_click"
    assert len(loaded["segments"]) == 5


def test_repository_creates_script_versions_table_idempotently(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.initialize()

    with repository.engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(script_versions)"))}

    assert {"project_id", "version", "script_json", "evaluation_json", "created_at", "updated_at"}.issubset(columns)


def test_migrator_generates_valid_script_and_records_warnings(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    repository.create_asset(
        project_id="proj-1",
        name="product.txt",
        asset_type="text",
        file_path=None,
        tag="产品特写",
        analysis={"description": "产品特写 功能 包装"},
    )
    payload = final_script_payload(version="high_conversion", bad_asset=True)
    client = FakeJsonClient([payload])
    service = MigratorService(repository, client=client)

    script = service.generate("proj-1", style="high_conversion")
    loaded = repository.get_project_script("proj-1")

    assert script.version == "high_conversion"
    assert len(script.segments) == 5
    assert script.segments[0].asset_id is None
    assert any("asset-missing" in warning for warning in script.metadata["warnings"])
    assert loaded is not None
    assert loaded["version"] == "high_conversion"
    assert "Premium sleep earbuds" in client.prompts[0]


def test_migrator_derives_segment_source_from_asset_origin(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    uploaded = repository.create_asset(
        project_id="proj-1",
        name="hook.jpg",
        asset_type="image",
        file_path=None,
        tag="冲突画面",
        analysis={"description": "冲突画面"},
        origin="uploaded",
    )
    packaging = repository.create_asset(
        project_id="proj-1",
        name="cta.png",
        asset_type="image",
        file_path=None,
        tag="优惠购买",
        analysis={"description": "包装补全"},
        origin="packaging",
    )
    payload = final_script_payload(version="high_click")
    payload["segments"][0]["asset_id"] = uploaded["id"]
    payload["segments"][-1]["asset_id"] = packaging["id"]

    script = MigratorService(repository, client=FakeJsonClient([payload])).generate("proj-1", style="high_click")

    assert script.segments[0].source == "original"
    assert script.segments[-1].source == "packaging"


def test_migrator_uses_short_description_fallback_and_warns(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, name="Headphones Pro", description="AI")
    client = FakeJsonClient([final_script_payload(version="fast_pace")])
    service = MigratorService(repository, client=client)

    script = service.generate("proj-1", style="fast_pace")

    assert script.version == "fast_pace"
    assert "Headphones Pro" in client.prompts[0]
    assert "项目名称" in script.metadata["warnings"][0]


def test_migrator_prefers_structured_project_brief(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="legacy description")
    repository.update_project(
        "proj-1",
        brief={
            "productName": "静谧 Pro 耳机",
            "sellingPoints": ["主动降噪", "续航 40 小时"],
            "targetAudience": "高频差旅用户",
            "offer": "首发立减 100 元",
            "tone": "理性高级",
            "mandatoryClaims": ["支持七天无理由"],
        },
    )
    client = FakeJsonClient([final_script_payload(version="high_quality")])

    MigratorService(repository, client=client).generate("proj-1", style="high_quality")

    assert "静谧 Pro 耳机" in client.prompts[0]
    assert "首发立减 100 元" in client.prompts[0]
    assert "legacy description" not in client.prompts[0]


def test_migrator_requires_product_information(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, name="Untitled", description="")
    service = MigratorService(repository, client=FakeJsonClient([final_script_payload()]))

    with pytest.raises(MigrationInputError, match="请补充商品信息"):
        service.generate("proj-1")


def test_migrator_retries_invalid_llm_output_three_times(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="A focused product description")
    client = FakeJsonClient([{"bad": "payload"}, {"still": "bad"}, {"wrong": "again"}])
    service = MigratorService(repository, client=client)

    with pytest.raises(MigrationError, match="valid FinalScript"):
        service.generate("proj-1")

    assert client.calls == 3


def test_migrate_routes_generate_variants_and_read_saved_script(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="A premium headphone launch for remote workers")
    client = FakeJsonClient([
        final_script_payload(version="high_click"),
        final_script_payload(version="high_quality", script_suffix=" with cinematic polish"),
    ])
    app = FastAPI()
    app.include_router(build_migrate_router(repository, client=client))
    test_client = TestClient(app)

    generated = test_client.post("/api/v1/migrate/proj-1", json={"style": "high_click"})
    variant = test_client.post("/api/v1/migrate/proj-1/variant", json={"style": "high_quality"})
    saved = test_client.get("/api/v1/migrate/proj-1")

    assert generated.status_code == 200
    assert generated.json()["version"] == "high_click"
    assert variant.status_code == 200
    assert variant.json()["version"] == "high_quality"
    assert saved.status_code == 200
    assert saved.json()["version"] == "high_quality"
    assert "cinematic polish" in saved.json()["segments"][0]["script"]


def test_migrate_versions_return_baseline_and_only_generated_variants(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="A premium headphone launch for remote workers")
    app = FastAPI()
    app.include_router(
        build_migrate_router(
            repository,
            client=FakeJsonClient([final_script_payload(version="high_click")]),
        )
    )
    client = TestClient(app)

    client.post("/api/v1/migrate/proj-1", json={"style": "high_click"})
    response = client.get("/api/v1/migrate/proj-1/versions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluationLabel"] == "结构规则评估"
    assert payload["baseline"]["id"] == "original"
    assert [version["id"] for version in payload["versions"]] == ["high_click"]
    assert payload["versions"][0]["timeline"][0]["source"] == "packaging"
    assert set(payload["versions"][0]["metrics"]) == {
        "scoreDelta",
        "materialCoverage",
        "productExposure",
        "gapCount",
        "ctaDuration",
    }
    assert payload["versions"][0]["metrics"]["materialCoverage"] == {
        "before": "100%",
        "after": "100%",
        "delta": "+0%",
        "positive": True,
    }
    assert payload["versions"][0]["metrics"]["productExposure"]["before"] == "8.0s"


def test_migrate_routes_return_404_and_422(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(project_id="proj-no-structure", name="Headphones", description="Useful product info", status="draft")
    repository.upsert_project(project_id="proj-no-info", name="Untitled", description="", status="editing", current_structure=five_segment_structure())
    app = FastAPI()
    app.include_router(build_migrate_router(repository, client=FakeJsonClient([final_script_payload()])))
    client = TestClient(app)

    assert client.post("/api/v1/migrate/missing", json={}).status_code == 404
    assert client.post("/api/v1/migrate/proj-no-structure", json={}).status_code == 422
    response = client.post("/api/v1/migrate/proj-no-info", json={})
    assert response.status_code == 422
    assert response.json()["detail"] == "请补充商品信息"
    assert client.get("/api/v1/migrate/proj-no-info").status_code == 404


def seeded_repository(
    tmp_path: Path,
    *,
    name: str = "Headphones",
    description: str = "Premium wireless headphones for office workers",
) -> SQLiteRepository:
    repository = SQLiteRepository(tmp_path / "structforge.db")
    repository.initialize()
    repository.upsert_project(
        project_id="proj-1",
        name=name,
        description=description,
        status="editing",
        analysis_result=five_segment_structure(),
        current_structure=five_segment_structure(),
    )
    return repository


def five_segment_structure() -> dict[str, Any]:
    payload = valid_video_structure_payload()
    payload["script"] = [
        _segment("seg-1", "hook", "Hook", 0, 3),
        _segment("seg-2", "pain", "Pain", 3, 8),
        _segment("seg-3", "product", "Product", 8, 12),
        _segment("seg-4", "proof", "Proof", 12, 24),
        _segment("seg-5", "cta", "CTA", 24, 35),
    ]
    return payload


def _segment(segment_id: str, segment_type: str, label: str, start: float, end: float) -> dict[str, Any]:
    return {
        "id": segment_id,
        "type": segment_type,
        "label": label,
        "start": start,
        "end": end,
        "duration": end - start,
        "goal": f"{segment_type}_goal",
        "copy": f"{label} source copy",
        "visual": f"{label} source visual",
        "healthScore": 80,
    }


def final_script_payload(
    *,
    version: str = "default",
    bad_asset: bool = False,
    script_suffix: str = "",
) -> dict[str, Any]:
    asset_id = "asset-missing" if bad_asset else None
    segments = [
        _final_segment("seg-1", "hook", 0, 3, asset_id, script_suffix),
        _final_segment("seg-2", "pain", 3, 8, None, script_suffix),
        _final_segment("seg-3", "product", 8, 12, None, script_suffix),
        _final_segment("seg-4", "proof", 12, 24, None, script_suffix),
        _final_segment("seg-5", "cta", 24, 35, None, script_suffix),
    ]
    return {
        "version": version,
        "total_duration": 35,
        "segments": segments,
        "metadata": {"warnings": [], "generated_at": "2026-05-23T00:00:00Z"},
    }


def _final_segment(
    segment_id: str,
    segment_type: str,
    start: float,
    end: float,
    asset_id: str | None,
    script_suffix: str,
) -> dict[str, Any]:
    return {
        "id": segment_id,
        "type": segment_type,
        "start": start,
        "end": end,
        "duration": end - start,
        "script": f"{segment_type} generated copy{script_suffix}",
        "visual": f"{segment_type} generated visual",
        "asset_id": asset_id,
        "subtitle_style": "clean_caption",
        "transition": "hard_cut",
        "locked": False,
    }
