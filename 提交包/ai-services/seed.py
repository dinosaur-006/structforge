"""Seed a demo project so first-time users can explore every page without uploading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript, VideoStructure


DEMO_STRUCTURE: dict[str, Any] = {
    "meta": {
        "duration": 35.0,
        "resolution": "1080x1920",
        "shots": 12,
        "coverLabel": "产品特写封面",
    },
    "script": [
        {
            "id": "seg-hook",
            "type": "hook",
            "label": "Hook",
            "start": 0.0,
            "end": 3.0,
            "duration": 3.0,
            "goal": "stop_scroll",
            "copy": "你以为这是普通耳机？",
            "visual": "产品特写旋转 + 快速缩放",
            "healthScore": 87,
            "subtitlePreset": "黄字白描边",
            "transition": "硬切",
            "beatAligned": True,
        },
        {
            "id": "seg-pain",
            "type": "pain",
            "label": "痛点",
            "start": 3.0,
            "end": 8.0,
            "duration": 5.0,
            "goal": "problem_awareness",
            "copy": "通勤噪音让你每天都很烦",
            "visual": "地铁人群与表情特写",
            "healthScore": 74,
            "subtitlePreset": "黄字白描边",
            "transition": "左滑",
        },
        {
            "id": "seg-product",
            "type": "product",
            "label": "产品引入",
            "start": 8.0,
            "end": 12.1,
            "duration": 4.1,
            "goal": "solution_intro",
            "copy": "这个降噪舱把声音隔开",
            "visual": "耳机开盒与降噪波纹",
            "healthScore": 62,
            "transition": "缩放",
        },
        {
            "id": "seg-proof",
            "type": "proof",
            "label": "卖点证明",
            "start": 12.1,
            "end": 24.0,
            "duration": 11.9,
            "goal": "benefit_proof",
            "copy": "双芯片降噪，人声也能清楚",
            "visual": "功能对比分屏与参数标签",
            "healthScore": 48,
            "transition": "硬切",
        },
        {
            "id": "seg-cta",
            "type": "cta",
            "label": "CTA",
            "start": 24.0,
            "end": 35.0,
            "duration": 11.0,
            "goal": "conversion",
            "copy": "现在预约，前100名送耳塞套装",
            "visual": "价格卡 + 购买按钮动画",
            "healthScore": 39,
            "transition": "硬切",
        },
    ],
    "rhythm": [
        {"second": 0.0, "cuts": 4, "emotion": 0.78},
        {"second": 5.0, "cuts": 5, "emotion": 0.71},
        {"second": 10.0, "cuts": 3, "emotion": 0.63},
        {"second": 15.0, "cuts": 6, "emotion": 0.86},
        {"second": 18.0, "cuts": 8, "emotion": 0.92, "highlight": True},
        {"second": 25.0, "cuts": 4, "emotion": 0.74},
        {"second": 35.0, "cuts": 3, "emotion": 0.69},
    ],
    "packaging": {
        "subtitleStyle": ["粗体无衬线", "黄字白描边", "居中偏下", "高覆盖密度"],
        "transitions": ["硬切 70%", "左滑 20%", "缩放 10%"],
        "overlays": ["产品标签贴纸", "价格角标", "箭头强调"],
    },
    "health": {
        "hook_strength": 87,
        "product_exposure_timing": 62,
        "selling_point_proof": 48,
        "pacing_compactness": 81,
        "cta_persuasiveness": 39,
        "overall": 72,
    },
}

DEMO_SCRIPT: dict[str, Any] = {
    "version": "default",
    "total_duration": 35.0,
    "segments": [
        {
            "id": "seg-hook",
            "type": "hook",
            "start": 0.0,
            "end": 3.0,
            "duration": 3.0,
            "script": "你还在忍受通勤噪音吗？",
            "visual": "产品特写旋转 + 快速缩放",
            "asset_id": None,
            "subtitle_style": "黄字白描边",
            "transition": "硬切",
            "locked": False,
            "source": "original",
        },
        {
            "id": "seg-pain",
            "type": "pain",
            "start": 3.0,
            "end": 8.0,
            "duration": 5.0,
            "script": "地铁上、办公室里，噪音让每一天都疲惫不堪。",
            "visual": "地铁人群与表情特写",
            "asset_id": None,
            "subtitle_style": "黄字白描边",
            "transition": "左滑",
            "locked": False,
            "source": "original",
        },
        {
            "id": "seg-product",
            "type": "product",
            "start": 8.0,
            "end": 12.1,
            "duration": 4.1,
            "script": "StructForge 降噪舱，内置双芯片主动降噪，一秒进入专注模式。",
            "visual": "耳机开盒与降噪波纹",
            "asset_id": None,
            "subtitle_style": "白字黑阴影",
            "transition": "缩放",
            "locked": False,
            "source": "original",
        },
        {
            "id": "seg-proof",
            "type": "proof",
            "start": 12.1,
            "end": 24.0,
            "duration": 11.9,
            "script": "实测对比：普通耳机 vs 降噪舱。人声、风声、地铁声，统统隔离。续航40小时，一周只充一次。",
            "visual": "功能对比分屏与参数标签",
            "asset_id": None,
            "subtitle_style": "白字黑阴影",
            "transition": "硬切",
            "locked": False,
            "source": "original",
        },
        {
            "id": "seg-cta",
            "type": "cta",
            "start": 24.0,
            "end": 35.0,
            "duration": 11.0,
            "script": "现在预约，前100名送限定耳塞套装。点击下方链接，马上锁定名额。",
            "visual": "价格卡 + 购买按钮动画",
            "asset_id": None,
            "subtitle_style": "黄字白描边",
            "transition": "硬切",
            "locked": False,
            "source": "original",
        },
    ],
    "metadata": {
        "restructure_needed": False,
        "edit_reason": "未收到明确的结构重排建议，已保持样例段落顺序与时长。",
        "warnings": ["请上传产品图片或视频素材以提升分镜可视化效果"],
        "generated_at": "",
    },
}


def _ensure_utc_timestamp(script: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone

    metadata = dict(script.get("metadata") or {})
    if not metadata.get("generated_at"):
        metadata["generated_at"] = datetime.now(timezone.utc).isoformat()
    script["metadata"] = metadata
    return script


def create_demo_projects(repository: SQLiteRepository) -> list[str]:
    """Create 3 demo projects across different product categories."""
    return [
        _create_demo(repository, "StructForge Demo — 降噪耳机", "无线主动降噪蓝牙耳机，40h续航，适合通勤与办公。",
            {"productName": "StructForge 降噪舱 Pro", "sellingPoints": ["双芯片主动降噪", "40小时续航", "蓝牙5.3低延迟", "记忆海绵耳塞"],
             "targetAudience": "通勤白领与学生", "offer": "前100名送限定耳塞套装", "tone": "专业可信，略带紧迫", "mandatoryClaims": ["数据来自实验室测试"]}),
        _create_demo(repository, "美妆Demo — 气垫粉底", "轻薄持妆气垫，适合日常通勤与约会。",
            {"productName": "轻透无瑕气垫霜 SPF50", "sellingPoints": ["12小时持妆", "轻薄透气", "遮瑕不假面", "含烟酰胺养肤"],
             "targetAudience": "25-35岁都市女性", "offer": "买一送一，限时加赠美妆蛋", "tone": "精致温柔，姐妹推荐感", "mandatoryClaims": []}),
        _create_demo(repository, "食品Demo — 元气森林", "草本植物饮料，真材实料煮出来的健康饮品。",
            {"productName": "元气森林好自在 草本饮品系列", "sellingPoints": ["四种口味全覆盖", "真材实料熬煮", "配料表干净", "0添加蔗糖"],
             "targetAudience": "注重健康的年轻消费者", "offer": "年货节2箱30瓶到手129.8元", "tone": "亲切活力，健康生活", "mandatoryClaims": []}),
    ]


def _create_demo(repository: SQLiteRepository, name: str, description: str, brief: dict) -> str:
    """Create a single demo project with the given name, description, and brief."""
    from uuid import uuid4

    project_id = str(uuid4())
    structure = VideoStructure.model_validate(DEMO_STRUCTURE)
    script = FinalScript.model_validate(_ensure_utc_timestamp(DEMO_SCRIPT))

    # Write project directly so all fields are in place atomically.
    repository.upsert_project(
        project_id=project_id,
        name=name,
        description=description,
        brief=brief,
        status="editing",
        analysis_result=structure,
        current_structure=structure,
        undo_stack=[],
        redo_stack=[],
        reference_job_id=None,
    )

    # Create sample analysis jobs so the analysis page shows sample cards.
    import json
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    from models.repository import analysis_jobs

    job_id = f"demo-job-{uuid4().hex[:8]}"
    with repository.engine.begin() as connection:
        connection.execute(
            analysis_jobs.insert().values(
                job_id=job_id,
                project_id=project_id,
                status="completed",
                progress=100,
                stage="Analysis completed",
                source_path="",
                result_json=json.dumps(
                    structure.model_dump(mode="json", by_alias=True),
                    ensure_ascii=False,
                ),
                error=None,
                created_at=now,
                updated_at=now,
            )
        )

    # Set the demo job as the reference.
    repository.select_reference_job(project_id, job_id)

    # Create placeholder assets.
    _create_demo_assets(repository, project_id)

    # Save the demo script.
    repository.save_project_script(project_id, script)
    from services.result_evaluator import ResultEvaluator

    evaluator = ResultEvaluator()
    repository.save_script_version(
        project_id,
        script,
        evaluator.evaluate_script(script),
    )

    return project_id


def _create_demo_assets(repository: SQLiteRepository, project_id: str) -> None:
    demo_assets: list[dict[str, Any]] = [
        {
            "name": "产品特写.png",
            "type": "image",
            "tag": "产品特写",
            "origin": "uploaded",
            "analysis": {
                "description": "降噪耳机产品特写展示",
                "tags": ["产品特写", "降噪"],
                "ocr_text": "",
            },
        },
        {
            "name": "通勤场景.mp4",
            "type": "video",
            "tag": "痛点场景",
            "origin": "uploaded",
            "analysis": {
                "description": "地铁通勤人群场景",
                "tags": ["痛点场景", "通勤"],
                "ocr_text": "",
            },
        },
        {
            "name": "功能演示片段.mp4",
            "type": "video",
            "tag": "演示证明",
            "origin": "uploaded",
            "analysis": {
                "description": "降噪功能对比演示",
                "tags": ["演示证明", "对比"],
                "ocr_text": "主动降噪 40dB",
            },
        },
        {
            "name": "卖点文案.txt",
            "type": "text",
            "tag": "优惠购买",
            "origin": "uploaded",
            "analysis": {
                "description": "核心卖点与价格信息文案",
                "tags": ["优惠购买", "CTA"],
                "ocr_text": "前100名送耳塞套装 限时优惠",
            },
        },
    ]
    for asset in demo_assets:
        repository.create_asset(
            project_id=project_id,
            name=asset["name"],
            asset_type=asset["type"],
            file_path=None,
            tag=asset["tag"],
            analysis=asset["analysis"],
            origin=asset["origin"],
        )


def create_demo_project(repository: SQLiteRepository) -> str:
    """Single demo project (backward compatibility)."""
    return create_demo_projects(repository)[0]


def seed_if_empty(settings: Settings) -> str | None:
    """If the DB has no projects, seed a demo project. Returns the project ID or None."""
    if not settings.seed_demo:
        return None

    repository = SQLiteRepository(settings.db_path)
    repository.initialize()

    existing = repository.list_projects()
    if existing:
        return None

    project_ids = create_demo_projects(repository)
    return project_ids[0] if project_ids else None
