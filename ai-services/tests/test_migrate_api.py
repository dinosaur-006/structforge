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


def test_migrator_preserves_explicit_reference_video_binding(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    source = repository.create_asset(
        project_id="proj-1",
        name="reference-source.mp4",
        asset_type="video",
        file_path=str(tmp_path / "reference-source.mp4"),
        tag="参考样例原片",
        analysis={"reference_source": True, "reference_job_id": "job-1"},
        origin="uploaded",
    )
    structure = five_segment_structure()
    structure["script"][0]["assetId"] = source["id"]
    repository.upsert_project(project_id="proj-1", status="editing", current_structure=structure)
    payload = final_script_payload(version="high_click")
    payload["segments"][0]["asset_id"] = None

    script = MigratorService(repository, client=FakeJsonClient([payload])).generate("proj-1", style="high_click")

    assert script.segments[0].asset_id == source["id"]
    assert script.segments[0].source == "original"


def test_migrator_preserves_reference_timeline_when_llm_changes_timing(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    source = repository.create_asset(
        project_id="proj-1",
        name="reference-source.mp4",
        asset_type="video",
        file_path=str(tmp_path / "reference-source.mp4"),
        tag="reference video",
        analysis={"reference_source": True, "reference_job_id": "job-1"},
        origin="uploaded",
    )
    structure = five_segment_structure()
    structure["script"][0]["assetId"] = source["id"]
    repository.upsert_project(project_id="proj-1", status="editing", current_structure=structure)
    payload = final_script_payload(version="default")
    payload["segments"][0]["start"] = 1.0
    payload["segments"][0]["end"] = 4.0

    script = MigratorService(repository, client=FakeJsonClient([payload])).generate("proj-1", style="default")

    assert script.segments[0].start == 0.0
    assert script.segments[0].end == 3.0
    assert script.segments[0].duration == 3.0


def test_high_click_style_does_not_force_reorder_without_ai_decision(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    source = repository.create_asset(
        project_id="proj-1",
        name="reference-source.mp4",
        asset_type="video",
        file_path=str(tmp_path / "reference-source.mp4"),
        tag="reference video",
        analysis={"reference_source": True, "reference_job_id": "job-1"},
        origin="uploaded",
    )
    structure = five_segment_structure()
    for segment in structure["script"]:
        segment["assetId"] = source["id"]
    repository.upsert_project(project_id="proj-1", status="editing", current_structure=structure)

    script = MigratorService(
        repository,
        client=FakeJsonClient([final_script_payload(version="high_click")]),
    ).generate("proj-1", style="high_click")

    assert [segment.type for segment in script.segments[:3]] == ["hook", "pain", "product"]
    assert script.segments[0].duration == 3.0
    assert script.segments[1].source_start == 3.0
    assert script.metadata["restructure_needed"] is False
    assert "edit_plan" not in script.metadata


def test_ai_restructure_decision_applies_proposed_order_and_source_ranges(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    source = repository.create_asset(
        project_id="proj-1",
        name="reference-source.mp4",
        asset_type="video",
        file_path=str(tmp_path / "reference-source.mp4"),
        tag="reference video",
        analysis={"reference_source": True, "reference_job_id": "job-1"},
        origin="uploaded",
    )
    structure = five_segment_structure()
    for segment in structure["script"]:
        segment["assetId"] = source["id"]
    repository.upsert_project(project_id="proj-1", status="editing", current_structure=structure)
    payload = final_script_payload(version="high_click")
    payload["segments"] = [
        {**payload["segments"][0], "duration": 2.0, "end": 2.0},
        {**payload["segments"][2], "start": 2.0, "end": 6.0, "duration": 4.0},
        {**payload["segments"][1], "start": 6.0, "end": 11.0, "duration": 5.0},
        *payload["segments"][3:],
    ]
    payload["metadata"].update(
        {
            "restructure_needed": True,
            "edit_reason": "产品真实露出过晚，应在 Hook 后立即展示。",
            "edit_plan": ["缩短 Hook", "将产品露出前移到第二段"],
        }
    )

    script = MigratorService(repository, client=FakeJsonClient([payload])).generate("proj-1", style="high_click")

    assert [segment.type for segment in script.segments[:3]] == ["hook", "product", "pain"]
    assert script.segments[0].duration == 2.0
    assert script.segments[1].start == 2.0
    assert script.segments[1].source_start == 8.0
    assert script.segments[1].source_end == 12.0
    assert script.metadata["edit_reason"] == "产品真实露出过晚，应在 Hook 后立即展示。"


def test_migrator_repairs_legacy_reference_project_before_generation(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path, description="Premium sleep earbuds for busy professionals")
    repository.create_job("job-legacy", str(tmp_path / "reference-source.mp4"), "proj-1")
    repository.update_job("job-legacy", status="completed", progress=100, result=five_segment_structure())
    repository.upsert_project(project_id="proj-1", status="editing", reference_job_id="job-legacy")

    script = MigratorService(
        repository,
        client=FakeJsonClient([final_script_payload(version="high_click")]),
    ).generate("proj-1", style="high_click")

    source_asset = next(
        asset for asset in repository.list_assets("proj-1")
        if (asset.get("analysis") or {}).get("reference_source") is True
    )
    structure = repository.get_project("proj-1")["current_structure"]
    assert all(segment["assetId"] == source_asset["id"] for segment in structure["script"])
    assert all(segment.asset_id == source_asset["id"] for segment in script.segments)
    assert script.segments[1].source_start == 3.0


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


def test_migrator_retries_invalid_llm_output_then_falls_back(tmp_path: Path) -> None:
    """After 3 invalid LLM outputs, gracefully falls back to template-based script."""
    repository = seeded_repository(tmp_path, description="A focused product description")
    client = FakeJsonClient([{"bad": "payload"}, {"still": "bad"}, {"wrong": "again"}])
    service = MigratorService(repository, client=client)

    # Should NOT raise — fallback script is returned after all retries fail.
    script = service.generate("proj-1")
    assert script is not None
    assert len(script.segments) > 0
    assert client.calls == 3
    # Fallback metadata confirms LLM was unavailable.
    metadata = script.metadata or {}
    warnings = [str(w) for w in (metadata.get("warnings") or [])]
    assert any("LLM" in w or "AI" in w for w in warnings) or "LLM" in str(metadata.get("edit_reason", ""))


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


# ── Product name pollution guard tests ──

BEAUTY_POLLUTANTS = [
    "洗面奶", "洁面", "护肤", "面霜", "精华液", "爽肤水", "乳液",
    "粉底", "口红", "眼影", "卸妆", "面膜", "防晒霜", "BB霜",
    "化妆水", "隔离霜", "素颜霜", "气垫", "散粉", "腮红",
]

FOOD_KEYWORDS = [
    "食材特写", "酱汁流淌", "冒泡沸腾", "油炸翻滚", "调味撒粉",
    "拉丝芝士", "切面展示", "麻辣红油", "叠放展示", "手撕特写",
    "蒸腾热气", "冰霜质感", "颗粒质感", "金黄酥脆", "Q弹质感",
]


def test_extract_product_identity_from_brief():
    """产品名从 project brief 正确提取"""
    from services.migrator import _extract_product_identity

    payload = {
        "project": {
            "product_info": {
                "productName": "麻辣王子辣条",
                "sellingPoints": ["麻辣鲜香", "独立小包装", "追剧必备"],
                "tone": "食欲大开",
            },
        },
    }
    identity = _extract_product_identity(payload)
    assert identity["name"] == "麻辣王子辣条"
    assert "麻辣鲜香" in identity["points"]
    assert identity["tone"] == "食欲大开"


def test_extract_product_identity_from_structure_meta():
    """产品名从 structure.meta.productName 正确提取"""
    from services.migrator import _extract_product_identity

    payload = {
        "project": {},
        "structure": {"meta": {"productName": "辣条大礼包 500g"}},
    }
    identity = _extract_product_identity(payload)
    assert identity["name"] == "辣条大礼包 500g"


def test_extract_product_identity_rejects_unknown():
    """未知商品不会被当作有效产品名"""
    from services.migrator import _extract_product_identity

    for bad_name in ("未知商品", "未识别（无语音）", ""):
        payload = {
            "project": {},
            "structure": {"meta": {"productName": bad_name}},
        }
        identity = _extract_product_identity(payload)
        # Falls back to project name or 未指定产品
        assert identity["name"] != bad_name


def test_food_video_not_polluted_by_beauty_keywords():
    """食品视频的迁移脚本不应包含美妆品类词汇"""
    from services.migrator import _extract_product_identity

    # Simulate a food video structure
    payload = {
        "project": {
            "name": "辣条广告视频",
            "product_info": {
                "productName": "麻辣辣条",
                "sellingPoints": ["麻辣口感", "追剧零食"],
                "tone": "食欲大开",
            },
        },
        "structure": {
            "meta": {
                "productName": "麻辣辣条",
                "duration": 30.0,
                "resolution": "1080x1920",
                "shots": 10,
                "coverLabel": "辣条特写",
            },
            "script": [
                {
                    "id": "seg-1", "type": "hook",
                    "copy": "这个辣条真的绝了！",
                    "visual": "金黄辣条特写，红油闪亮",
                    "visual_keywords": ["食材特写", "麻辣红油", "金黄酥脆"],
                },
            ],
        },
    }

    # Verify product identity is food, not beauty
    identity = _extract_product_identity(payload)
    assert identity["name"] == "麻辣辣条"
    for pollutant in BEAUTY_POLLUTANTS:
        assert pollutant not in identity["name"], f"产品名被污染: {pollutant}"

    # Verify the structure's visual keywords are food-related, not beauty
    script = payload["structure"]["script"]
    for seg in script:
        for kw in seg.get("visual_keywords", []):
            assert kw in FOOD_KEYWORDS or kw not in [
                "瓶身特写", "膏体拉丝", "泡沫细腻", "挤压出液"
            ], f"食品分镜出现美妆关键词: {kw}"


def test_build_local_structure_preserves_product_name():
    """LLM 回退结构应保留从 prompt_context 提取的 productName"""
    from services.llm_structure import build_local_structure_payload

    # Food context — should preserve product name
    food_context = {
        "meta": {
            "duration": 30.0,
            "resolution": "1080x1920",
            "shots": 10,
            "productName": "麻辣辣条 大包装",
        },
    }
    payload = build_local_structure_payload(food_context)
    assert payload["meta"]["productName"] == "麻辣辣条 大包装"

    # Empty context — should fall back to 未知商品
    empty_payload = build_local_structure_payload({})
    assert empty_payload["meta"]["productName"] == "未知商品"


def test_structure_meta_includes_product_name_after_normalization():
    """_normalize_structure 应为缺失 productName 的结构补上 未知商品"""
    from models.schemas import VideoStructure
    from services.llm_structure import _normalize_structure

    payload = {
        "meta": {"duration": 30.0, "resolution": "1080x1920", "shots": 10, "coverLabel": "test"},
        "script": [
            {"id": "seg-1", "type": "hook", "label": "Hook", "start": 0, "end": 3,
             "duration": 3, "goal": "stop", "copy": "test", "visual": "test",
             "visual_keywords": ["纯色背景"], "healthScore": 80},
        ],
        "rhythm": [
            {"second": 0, "cuts": 2, "emotion": 0.5},
            {"second": 5, "cuts": 2, "emotion": 0.5},
            {"second": 10, "cuts": 2, "emotion": 0.5},
            {"second": 15, "cuts": 2, "emotion": 0.5},
            {"second": 20, "cuts": 2, "emotion": 0.5},
            {"second": 25, "cuts": 2, "emotion": 0.5},
        ],
        "packaging": {"subtitleStyle": ["test"], "transitions": ["test"], "overlays": ["test"]},
        "health": {
            "hook_strength": 80, "product_exposure_timing": 80,
            "selling_point_proof": 80, "pacing_compactness": 80,
            "cta_persuasiveness": 80, "overall": 80,
        },
    }
    structure = VideoStructure.model_validate(payload)
    normalized = _normalize_structure(structure)
    assert normalized.meta.productName == "未知商品"


def test_food_visual_keywords_exist_in_whitelist():
    """验证食品关键词已加入白名单（防止回退）"""
    from services.llm_structure import PROMPT_TEMPLATE
    for kw in FOOD_KEYWORDS:
        assert kw in PROMPT_TEMPLATE, (
            f"食品关键词 '{kw}' 不在 PROMPT_TEMPLATE 白名单中。"
            f"请在 llm_structure.py 的视觉特征词库中补充。"
        )
