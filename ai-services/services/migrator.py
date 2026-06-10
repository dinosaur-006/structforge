from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript, FinalScriptStyle, ResultEvaluation, ResultVersionsResponse, VideoStructure
from services.gap_detector import GapDetector
from services.llm_structure import DoubaoSeedClient, JsonCompletionClient, StructureExtractionError
from services.reference_assets import bind_reference_video_asset
from services.result_evaluator import ResultEvaluator
from services.content_safety import ContentSafetyService
from services.overlay_advisor import OverlayAdvisor


STYLE_INSTRUCTIONS: dict[str, str] = {
    "default": "保持原结构节奏，输出清晰、专业、可直接执行的分镜脚本。",
    "high_click": "强化前三秒冲突和停留理由，Hook 文案更短、更尖锐，字幕更醒目。",
    "high_conversion": "强化信任背书、优惠理由和 CTA 紧迫感，结尾转化动作更明确。",
    "fast_pace": "整体文案更短，镜头节奏更快，转场更紧凑，但总时长仍需匹配结构。",
    "high_quality": "文案更精致克制，画面描述增加光影、材质和高级感，转场更平滑。",
    "xiaohongshu_ces": """小红书 CES 算法优化版。Hook和Pain段使用争议性提问。CTA段加互动引导。""",
    "wechat_social": """微信视频号社交裂变版。Proof/CTA段挂载社交资产卡片。文案植入转发引导。""",
}

# ── Quantified style parameters (replaces vague natural language) ──
STYLE_PARAMS: dict[str, dict] = {
    "default": {},
    "high_click": {
        "hook_duration_max_s": 2.0,
        "hook_camera_prefer": "快推",
        "hook_emotion_prefer": "惊讶",
        "hook_subtitle_anim": "弹入",
        "hook_pace": "快",
        "hook_visual_fx": "震屏",
    },
    "high_conversion": {
        "cta_duration_max_s": 3.0,
        "cta_emotion_prefer": "紧迫",
        "cta_pace": "快",
        "cta_subtitle_anim": "缩放出现",
        "proof_count_min": 3,
    },
    "fast_pace": {
        "hook_duration_max_s": 2.0,
        "all_shot_count_increase": 1,
        "all_pace_default": "快",
        "all_subtitle_anim": "弹入",
    },
    "high_quality": {
        "all_pace_default": "正常",
        "all_emotion_prefer": "亲切",
        "all_camera_prefer": "缓推",
        "all_visual_fx": "无",
    },
}


class MigrationNotFoundError(LookupError):
    pass


class MigrationInputError(ValueError):
    pass


class MigrationError(RuntimeError):
    pass


class MigratorService:
    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        settings: Settings | None = None,
        client: JsonCompletionClient | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or Settings()
        if client:
            self.client = client
        else:
            # Migration prompt is the largest in the system (full structure + assets + gaps).
            # Use a longer timeout than the default 90s.
            from services.llm_client import RobustLLMClient
            self.client = DoubaoSeedClient(
                self.settings,
                _client=RobustLLMClient(
                    str(self.settings.doubao_llm_endpoint or ""),
                    str(self.settings.doubao_llm_api_key or ""),
                    str(self.settings.doubao_llm_model),
                    timeout=120,  # migration needs more time than analysis
                ),
            )
        self.gap_detector = GapDetector(repository)
        self.evaluator = ResultEvaluator(
            llm_endpoint=self.settings.doubao_llm_endpoint,
            llm_api_key=self.settings.doubao_llm_api_key,
            llm_model=self.settings.doubao_llm_model,
        )

    def generate(self, project_id: str, style: FinalScriptStyle = "default") -> FinalScript:
        project = self.repository.get_project(project_id)
        if project is None:
            raise MigrationNotFoundError(f"Project not found: {project_id}")

        structure_payload = project.get("current_structure") or project.get("analysis_result")
        if not structure_payload:
            raise MigrationInputError("项目结构未初始化")
        structure = VideoStructure.model_validate(structure_payload)
        structure = self._bind_legacy_reference_source(project, structure)
        product_info, warnings = _product_info(project)
        assets = self.repository.list_assets(project_id)
        gaps = self.gap_detector.detect(project_id)

        # Slim the structure for the prompt — full model_dump includes
        # visual_keywords arrays that bloat the prompt to 5000+ tokens.
        # Keep only the fields the LLM actually needs for migration.
        slim_structure = {
            "meta": {
                "duration": structure.meta.duration,
                "productName": structure.meta.productName,
            },
            "script": [
                {
                    "id": s.id, "type": s.type, "label": s.label,
                    "start": s.start, "end": s.end, "duration": s.duration,
                    "goal": s.goal, "copy": s.copy_text, "visual": s.visual,
                    "healthScore": s.healthScore,
                    "shot_count": getattr(s, "shot_count", None),
                    "avg_shot_duration": getattr(s, "avg_shot_duration", None),
                }
                for s in structure.script
            ],
            "packaging": structure.packaging.model_dump(mode="json", by_alias=True),
            "health": structure.health.model_dump(mode="json", by_alias=True),
        }
        prompt_context = {
            "project": {
                "id": project["id"],
                "name": project["name"],
                "product_info": product_info,
            },
            "style": style,
            "style_instruction": STYLE_INSTRUCTIONS[style],
            "style_params": STYLE_PARAMS.get(style, {}),
            "structure": slim_structure,
            "original_scores": {
                "hook_strength": structure.health.hook_strength,
                "product_exposure_timing": structure.health.product_exposure_timing,
                "selling_point_proof": structure.health.selling_point_proof,
                "pacing_compactness": structure.health.pacing_compactness,
                "cta_persuasiveness": structure.health.cta_persuasiveness,
                "overall": structure.health.overall,
                "weakest_dimensions": _weakest_dimensions(structure),
            },
            "assets": [_asset_summary(asset) for asset in assets],
            "gaps": gaps,
            "constraints": {
                "allowed_asset_ids": [asset["id"] for asset in assets],
                "total_duration": structure.meta.duration,
                "segment_count": len(structure.script),
            },
        }
        script = self._generate_with_retries(prompt_context, style, structure, assets, warnings)

        # Enrich with overlay recommendations (rule-based, no LLM).
        overlay_advisor = OverlayAdvisor()
        seg_dicts_for_overlay = [s.model_dump(mode="json") for s in script.segments]
        overlay_recs = overlay_advisor.recommend_for_script(seg_dicts_for_overlay)
        if overlay_recs:
            existing_meta = dict(script.metadata or {})
            existing_meta["overlay_recommendations"] = overlay_recs
            script.metadata = existing_meta

        # Content safety check on generated script.
        if self.settings.content_safety_enabled:
            safety = ContentSafetyService(
                self.settings.content_safety_blocked_terms,
                llm_endpoint=self.settings.doubao_llm_endpoint,
                llm_api_key=self.settings.doubao_llm_api_key,
                llm_model=self.settings.doubao_llm_model,
            )
            result = safety.check_script(script.model_dump(mode="json"))
            if result.warnings:
                existing_warnings: list[str] = list(script.metadata.get("warnings") or [])
                script.metadata["warnings"] = [*existing_warnings, *[f"[安全检查] {w}" for w in result.warnings]]
            if result.blocked:
                raise MigrationError(f"内容安全检查阻止: {'; '.join(result.blocked)}")

        # ── Inject product identity into script metadata ──
        # This allows compositor to read product_name/type when calling AIVideoService
        product_identity = _extract_product_identity(prompt_context)
        existing_meta = dict(script.metadata or {})
        existing_meta.setdefault("productName", product_identity.get("name", ""))
        existing_meta.setdefault("productType", product_identity.get("category", "其他"))
        # Pass product image visual analysis to the render pipeline for Flux prompts
        project_brief = project.get("brief") or {}
        if isinstance(project_brief, dict) and project_brief.get("_productVisual"):
            existing_meta["productVisual"] = project_brief["_productVisual"]

        # Pre-generate Flux prompts for frontend display (rule-based, instant)
        try:
            from services.flux_prompt_generator import FluxPromptGenerator
            prompt_gen = FluxPromptGenerator(self.settings)
            product_visual = existing_meta.get("productVisual") or {}
            prompts_list = []
            for seg in script.segments:
                p = prompt_gen.generate(
                    segment_type=seg.type, script=seg.script or "",
                    visual=seg.visual or "", camera=getattr(seg, 'camera', '静态') or '静态',
                    emotion=getattr(seg, 'emotion', '亲切') or '亲切',
                    duration=float(seg.duration), product_name=product_identity.get("name", ""),
                    product_type=product_identity.get("category", "其他"),
                    product_vision_tags=product_visual.get("tags") if isinstance(product_visual, dict) else None,
                    product_vision_colors=product_visual.get("colors") if isinstance(product_visual, dict) else None,
                    width=1080, height=1920,
                )
                prompts_list.append({"segment_id": seg.id, "type": seg.type, "prompt": p})
            existing_meta["prompts"] = prompts_list
        except Exception:
            pass  # non-critical

        script.metadata = existing_meta
        self.repository.save_project_script(project_id, script)
        self.repository.save_script_version(project_id, script, self.evaluator.evaluate_script(script))
        return script

    def _bind_legacy_reference_source(self, project: dict[str, Any], structure: VideoStructure) -> VideoStructure:
        reference_job_id = project.get("reference_job_id")
        if not reference_job_id:
            return structure
        reference_job = self.repository.get_job(reference_job_id)
        if not reference_job or not reference_job.get("source_path"):
            return structure
        hydrated = bind_reference_video_asset(
            self.repository,
            project_id=project["id"],
            job_id=reference_job_id,
            source_path=reference_job["source_path"],
            structure=structure,
            fill_unbound_only=True,
        )
        if hydrated != structure:
            self.repository.upsert_project(
                project_id=project["id"],
                status=project["status"],
                current_structure=hydrated,
            )
        return hydrated

    def get_saved_script(self, project_id: str) -> FinalScript | None:
        if self.repository.get_project(project_id) is None:
            raise MigrationNotFoundError(f"Project not found: {project_id}")
        script = self.repository.get_project_script(project_id)
        return FinalScript.model_validate(script) if script else None

    def get_versions(self, project_id: str) -> ResultVersionsResponse:
        project = self.repository.get_project(project_id)
        if project is None:
            raise MigrationNotFoundError(f"Project not found: {project_id}")
        baseline_payload = project.get("analysis_result") or project.get("current_structure")
        if not baseline_payload:
            raise MigrationInputError("项目结构未初始化")
        baseline_structure = VideoStructure.model_validate(baseline_payload)
        baseline_evaluation = self.evaluator.evaluate_baseline(baseline_structure)
        return ResultVersionsResponse(
            evaluationLabel="结构规则评估",
            baseline=self.evaluator.baseline_version(baseline_structure),
            versions=[
                self.evaluator.script_version(
                    FinalScript.model_validate(saved["script"]),
                    baseline_evaluation,
                    ResultEvaluation.model_validate(saved["evaluation"]),
                )
                for saved in self.repository.list_script_versions(project_id)
            ],
        )

    def _generate_with_retries(
        self,
        prompt_context: dict[str, Any],
        style: str,
        structure: VideoStructure,
        assets: list[dict[str, Any]],
        base_warnings: list[str],
    ) -> FinalScript:
        import sys
        errors: list[str] = []
        max_attempts = self.settings.llm_max_attempts
        prompt_size = 0
        for attempt in range(1, max_attempts + 1):
            try:
                prompt = _build_prompt(prompt_context, attempt)
                prompt_size = len(prompt)
                import time as _time
                t0 = _time.monotonic()
                # Schema injection: LLM sees FinalScript format → fewer validation errors
                try:
                    raw_payload = self.client.complete_json(prompt, response_type=FinalScript)
                    script = raw_payload if isinstance(raw_payload, FinalScript) else None
                except Exception:
                    script = None
                if script is None:
                    raw_payload = self.client.complete_json(prompt)
                    if isinstance(raw_payload, str):
                        raw_payload = json.loads(raw_payload)
                    raw_payload = FinalScript._try_wrap_flat_llm_output(raw_payload)
                    script = FinalScript.model_validate(raw_payload)
                elapsed = _time.monotonic() - t0
                sys.stderr.write(f"[MIGRATE] LLM attempt {attempt}/{max_attempts}: prompt={prompt_size} chars, response in {elapsed:.1f}s\n")
                sys.stderr.flush()
                if script.version != style:
                    payload = script.model_dump(mode="json")
                    payload["version"] = style
                    script = FinalScript.model_validate(payload)
                return _normalize_script(script, structure, assets, base_warnings)
            except (json.JSONDecodeError, ValidationError, ValueError, StructureExtractionError) as exc:
                err_msg = str(exc)[:200]
                errors.append(err_msg)
                sys.stderr.write(f"[MIGRATE] ❌ attempt {attempt} failed: {err_msg}\n")
                sys.stderr.flush()

        # All attempts failed
        sys.stderr.write(f"[MIGRATE] ❌ ALL {max_attempts} attempts failed (prompt={prompt_size} chars). Errors:\n")
        for i, e in enumerate(errors):
            sys.stderr.write(f"[MIGRATE]   [{i+1}] {e[:200]}\n")
        sys.stderr.flush()

        fallback = _build_fallback_script(structure, assets, style, base_warnings)
        if fallback is not None:
            return fallback

        raise MigrationError(
            f"LLM failed to return a valid FinalScript after {max_attempts} attempts: "
            + " | ".join(errors[-3:])
        )


def _weakest_dimensions(structure: VideoStructure) -> list[str]:
    """Return the 2 weakest health dimensions for targeted improvement."""
    scores = [
        ("hook_strength", structure.health.hook_strength, "开头吸引力"),
        ("product_exposure_timing", structure.health.product_exposure_timing, "产品露出时机"),
        ("selling_point_proof", structure.health.selling_point_proof, "卖点证明力"),
        ("pacing_compactness", structure.health.pacing_compactness, "节奏紧凑度"),
        ("cta_persuasiveness", structure.health.cta_persuasiveness, "转化号召力"),
    ]
    scores.sort(key=lambda x: x[1])
    return [f"{name}({label})" for _, name, label in scores[:2]]


def _extract_product_identity(payload: dict[str, Any]) -> dict[str, str]:
    """Extract human-readable product identity for explicit prompt injection.

    Pulls from: brief > structure.meta.productName > ASR hint > project name.
    Filename patterns like "抖音202668 241811" are detected and rejected.
    """
    import re

    def _is_garbage_name(name: str) -> bool:
        """Detect platform-generated filenames that are NOT product names."""
        if not name or not name.strip():
            return True
        n = name.strip()
        # TikTok pattern: "抖音" + numbers
        if re.match(r'^抖音\d{4,}', n):
            return True
        # Pure numeric or "platform + numbers" pattern
        if re.match(r'^\d{8,}$', n):
            return True
        # Generic "download" or "video" prefixes
        if re.match(r'^(download|video|clip|record|screen|capture)[\-_]?\d+', n, re.IGNORECASE):
            return True
        return False

    # Priority 1: project brief (explicit user input)
    proj = payload.get("project") or {}
    prod_info = proj.get("product_info") or {}
    if isinstance(prod_info, dict) and str(prod_info.get("productName") or "").strip():
        pn = str(prod_info.get("productName", "")).strip()
        if not _is_garbage_name(pn):
            return {
                "name": pn,
                "category": str(prod_info.get("productType", prod_info.get("category", "未分类"))).strip(),
                "points": ", ".join([str(p) for p in (prod_info.get("sellingPoints") or [])][:5]) or "未指定",
                "tone": str(prod_info.get("tone", "专业可信")).strip(),
            }
    if isinstance(prod_info, str) and len(prod_info.strip()) >= 2 and not _is_garbage_name(prod_info.strip()):
        return {"name": prod_info.strip(), "category": "未分类", "points": "未指定", "tone": "专业可信"}

    # Priority 2: structure meta (LLM-extracted from the sample video)
    structure = payload.get("structure") or {}
    meta = structure.get("meta") or {}
    pn = str(meta.get("productName") or "").strip()
    if pn and pn not in ("", "未知商品", "未识别（无语音）") and not _is_garbage_name(pn):
        return {"name": pn, "category": "未分类", "points": "未指定", "tone": "专业可信"}

    # Priority 3: project name (from filename) — only if not garbage
    proj_name = str(proj.get("name") or "").strip()
    if proj_name and not _is_garbage_name(proj_name):
        return {"name": proj_name, "category": "未分类", "points": "未指定", "tone": "专业可信"}

    return {"name": "未指定产品", "category": "未分类", "points": "未指定", "tone": "专业可信"}


def _product_info(project: dict[str, Any]) -> tuple[str | dict[str, Any], list[str]]:
    brief = project.get("brief") or {}
    if str(brief.get("productName") or "").strip() or list(brief.get("sellingPoints") or []):
        return brief, []

    description = str(project.get("description") or "").strip()
    if len("".join(description.split())) >= 10:
        return description, []

    name = str(project.get("name") or "").strip()
    unavailable = {"", "untitled", "untitled project", "未命名项目", "新建项目"}
    if name.lower() not in unavailable and not name.lower().startswith("proj-"):
        return name, ["商品信息来自项目名称，建议补充项目描述"]

    raise MigrationInputError("请补充商品信息")


def _asset_summary(asset: dict[str, Any]) -> dict[str, Any]:
    analysis = asset.get("analysis") or {}
    return {
        "id": asset["id"],
        "name": asset["name"],
        "type": asset["type"],
        "tag": asset["tag"],
        "match_status": asset["match_status"],
        "match_score": asset["match_score"],
        "description": analysis.get("description"),
        "tags": analysis.get("tags", []),
    }


def _build_prompt(context: dict[str, Any], attempt: int) -> str:
    payload = dict(context)
    payload["attempt"] = attempt

    # ── Extract product identity for explicit injection ──
    product_identity = _extract_product_identity(payload)

    # ── Build L2 rhythm data for prompt injection ──
    rhythm_items = []
    for s in payload.get("structure", {}).get("script", []):
        sc = getattr(s, "shot_count", None) if isinstance(s, dict) else s.get("shot_count")
        avg = getattr(s, "avg_shot_duration", None) if isinstance(s, dict) else s.get("avg_shot_duration")
        avg_str = f"{avg:.1f}s" if avg else "?"
        rhythm_items.append({"id": s.get("id", s.id if hasattr(s, 'id') else '?'),
                             "type": s.get("type", s.type if hasattr(s, 'type') else '?'),
                             "shot_count": sc or "?", "avg_shot": avg_str})
    rhythm_json = json.dumps(rhythm_items, ensure_ascii=False, indent=2)

    return f"""
你是 StructForge 的首席视频脚本导演，你的任务是将爆款样例视频的**结构骨架和创作方法**迁移到新产品上，生成一条比原视频**更具爆款潜力**的新脚本。

## ⚠️ 目标产品（绝对不可改变）

你要为以下产品创作脚本：
**产品名称：{product_identity['name']}**
**产品品类：{product_identity['category']}**
**核心卖点：{product_identity['points']}**
**品牌调性：{product_identity['tone']}**

以上产品信息是铁律。脚本中的每一句口播文案、每一个画面描述都必须围绕这个产品。
严禁将产品替换为其他品类（如把食品写成护肤品、把电子写成美妆等）。
严禁使用与产品品类无关的视觉描述（如食品产品出现"挤压出液""泡沫细腻"）。

## 核心原则：你是在"迁移方法"，不是"改写文案"

原视频为什么能成为爆款？不是因为那几句文案，而是因为它遵循了一套**经过验证的说服心理学框架**：
- 第0-3秒用一个不可抗拒的钩子制造认知冲击
- 第3-8秒放大用户的痛点或渴望，让产品成为唯一的解药
- 第8-18秒展示产品，用具体细节让用户产生"想要"的冲动
- 第18-28秒用无可辩驳的证据摧毁购买犹豫
- 最后3-8秒用一个具体、有稀缺感、零风险的号召完成转化

你的工作是把这套框架**一模一样地应用**到新产品上，但文案、画面、情绪都要换成新产品相关的。

## 每个分镜的制作参数（独立字段输出，不要写在script里）

你在每个分镜中需要设定以下5个制作参数，它们各自有独立的JSON字段：

- camera（镜头运动）: 静态 / 缓推 / 快推 / 拉远 / 横移 / 跟随 / 手持微晃
- subtitle_anim（字幕动画）: 弹入 / 淡入 / 逐字出现 / 缩放出现 / 无动画
- pace（语速与节奏）: 快 / 正常 / 慢
- emotion（语气情感）: 惊讶 / 紧迫 / 亲切 / 权威 / 感动 / 兴奋 / 平静
- visual_fx（画面特效）: 无 / 震屏 / 闪白 / 慢动作 / 放大 / 模糊过渡

**重要：script字段只写口播文案本身，不要在里面加【镜】【字】等标记。这些参数用独立的JSON字段输出。**

## 分镜类型速查

| 类型 | 相机 | 情绪 | 语速 | 特效 | 文案要点 |
|------|------|------|------|------|------|
| Hook(≤3s) | 快推 | 惊讶 | 快 | 震屏 | 认知冲突, 0.3秒停滑, 短促冲击力 |
| Pain(3-5s) | 缓推 | 亲切 | 正常 | 无 | 具体场景共鸣, 第一人称, 让用户对号入座 |
| Product(≤5s) | 缓推 | 兴奋 | 正常 | 放大 | 英雄镜头, 具体可感知特性 |
| Proof(5-8s) | 横移 | 权威 | 正常 | 慢动作 | 对比/数据/实测证据 |
| CTA(≤4s) | 快推 | 紧迫 | 快 | 放大 | 行动指令+稀缺+零风险, 短句连续轰炸 |

硬性约束: Product段start≤5s, CTA段duration≤4s. Hook/CTA禁止静态镜头.

## 原视频镜头节奏（L2 结构） — 不可丢失

以下数据来自帧级场景检测，记录了原视频每段的镜头数和平均镜头时长：
{rhythm_json}

**节奏迁移规则**：
- Hook段必须保持快节奏（shot_count≥2，avg_shot≤1.5s）
- Pain段可适度放缓（avg_shot 1.5-2.5s），给用户共鸣空间
- Product段需展示细节（avg_shot≥2s），给画面停留时间
- CTA段必须快切（shot_count≥2，avg_shot≤1.5s）
- 新脚本中薄弱段落的 shot_count 应比原视频增加 1-2 个镜头以提升节奏

## 原视频健康度诊断

原视频评分（0-100，95%的视频综合分<65，75+已是专业水平）：
- 开头吸引力: {payload.get('original_scores', {}).get('hook_strength', '?')}
- 产品露出时机: {payload.get('original_scores', {}).get('product_exposure_timing', '?')}
- 卖点证明力: {payload.get('original_scores', {}).get('selling_point_proof', '?')}
- 节奏紧凑度: {payload.get('original_scores', {}).get('pacing_compactness', '?')}
- 转化号召力: {payload.get('original_scores', {}).get('cta_persuasiveness', '?')}
- 综合: {payload.get('original_scores', {}).get('overall', '?')}

最薄弱维度: {json.dumps(payload.get('original_scores', {}).get('weakest_dimensions', []), ensure_ascii=False)}

## 创作指导

原视频的 LLM 健康度评分指出了相对薄弱的维度。请在生成新脚本时：
- 重点关注薄弱维度的改进
- 保持原视频在优势维度上的表现
- 根据产品特性调整分镜类型的制作参数（已在分镜速查表中指定）

你需要运用自己的爆款创作知识，结合原视频的结构数据，自主判断如何优化每个分镜。

## 品牌调性与情绪共鸣参数

你必须根据产品类型和风格，在 metadata 中设置全局参数：

- brand_vibe（品牌调性）: 根据产品类型自动推断——
  食品饮料 → "治愈解压" / 美妆护肤 → "精致专业" / 数码电子 → "科技未来感" /
  服装配饰 → "时尚潮流" / 家居日用 → "沉浸式生活美学"
- emotional_resonance（情绪共鸣）: 根据风格推断——
  high_click → "高能炸裂" / high_quality → "温馨治愈" / fast_pace → "紧迫焦虑" /
  xiaohongshu_ces → "精致共鸣" / wechat_social → "干货信赖" / default → "专业亲切"

这些参数会联动下游渲染引擎自动匹配 BGM、滤镜和运镜风格。

## 风格指令: {payload.get('style_instruction', '')}

## 风格量化参数（硬性约束，必须执行）

以下参数来自用户选择的风格，**不是建议而是要求**。你必须按照这些参数设定对应的分镜字段：
{json.dumps(payload.get('style_params', {}), ensure_ascii=False, indent=2)}

参数说明：
- hook_duration_max_s: Hook段最长时间（超过则不合格）
- hook_camera_prefer: Hook段优先使用的运镜
- cta_duration_max_s: CTA段最长时间
- all_*: 所有段落的默认值

## 输出格式
严格JSON，所有文案必须是口语化中文，脚本中的人称和语气贴近目标受众。
{{
  "version": "high_click|high_conversion|fast_pace|high_quality|default",
  "total_duration": number,
  "segments": [
    {{
      "id": string,
      "type": "hook|pain|product|proof|cta",
      "start": number,
      "end": number,
      "duration": number,
      "script": "口播文案（纯文字，不含任何标记符号）",
      "visual": "画面描述",
      "camera": "静态|缓推|快推|拉远|横移|跟随|手持微晃",
      "subtitle_anim": "弹入|淡入|逐字出现|缩放出现|无动画",
      "pace": "快|正常|慢",
      "emotion": "惊讶|紧迫|亲切|权威|感动|兴奋|平静",
      "visual_fx": "无|震屏|闪白|慢动作|放大|模糊过渡",
      "subtitle_style": "白字黑边",
      "transition": "硬切",
      "asset_id": null,
      "locked": false
    }}
  ],
  "metadata": {{
    "restructure_needed": boolean,
    "edit_reason": string,
    "edit_plan": [string],
    "warnings": [string],
    "generated_at": string,
    "brand_vibe": "品牌调性（治愈解压/精致专业/科技未来感/时尚潮流/沉浸式生活美学）",
    "emotional_resonance": "情绪共鸣（高能炸裂/温馨治愈/紧迫焦虑/精致共鸣/干货信赖/专业亲切）",
    "migration_strategy": {{
      "preserved": ["列出你从原视频保留的结构特征，如'Hook段快节奏2镜头模式'、'CTA段紧迫感'"],
      "strengthened": ["列出你在新脚本中强化的特征及原因，如'产品露出从8s提前到5s——原视频healthScore显示产品露出时机=58分'"],
      "changed": ["列出你主动改变的特征及理由，如'Pain段从5段压缩为3段——原视频节奏紧凑度=70分'"],
      "strategy_brief": "一句话总结你的迁移策略"
    }}
  }},
  "timelineSpec": {{
    "composition": {{"fps": 30, "width": 1080, "height": 1920, "totalFrames": number, "durationSeconds": number}},
    "tracks": [
      {{"id": "video-track", "type": "video", "label": "视频", "clips": [
        {{"id": "clip-1", "startFrame": 0, "durationInFrames": 90, "component": "TitleCard|ProductHero|CTACard|SplitScreen|StatCard|QuoteCard|OverlayText", "props": {{...}}}}
      ]}},
      {{"id": "subtitle-track", "type": "subtitle", "label": "字幕", "clips": [{{"id": "s1", ...}}]}}
    ]
  }}
}}

## 硬性规则
- 保持样例的段落数和段落类型（几段就输出几段，独特的段落类型如"竞品对比"必须保留）
- 总时长与原结构偏差不超过10%
- 每个分镜的script是干净的口播文案，不含任何符号标记
- 结构重排必须有edit_reason说明理由
- **你的目标是生成一条比原视频更可能成为爆款的脚本。如果原视频某项得分低于60，你必须在该维度上给出明显更强的方案**
- **metadata.migration_strategy 必须认真填写** — 这是评审考核的关键指标。preserved 至少列出 2 项，strengthened 至少列出 2 项并注明原因（引用具体 healthScore 数据），changed 至少列出 1 项并说明理由

输入上下文：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def _build_fallback_script(
    structure: VideoStructure,
    assets: list[dict[str, Any]],
    style: str,
    base_warnings: list[str],
) -> FinalScript | None:
    """Build a basic script from the structure template when LLM is unavailable.

    Segments are marked with their actual source type:
    - 'original' if a matching uploaded asset exists
    - 'packaging' if no asset but packaging fallback could fill it
    - 'aigc' if no asset and packaging won't work (needs AI generation)
    """
    try:
        from models.schemas import FinalSegmentSource

        # Exclude reference video — it's the sample, not a user-uploaded content asset.
        # Reference-bound segments without user assets need AI generation.
        user_assets = [a for a in assets if a.get("file_path")
                       and not (a.get("analysis") or {}).get("reference_source")]
        asset_ids = [a["id"] for a in user_assets]
        segments = []
        for seg in structure.script:
            # Determine actual source based on USER asset availability.
            # User-matched → original. No match → aigc (needs AI generation).
            if seg.assetId and seg.assetId in asset_ids:
                source: FinalSegmentSource = "original"
            else:
                source: FinalSegmentSource = "aigc"

            segments.append({
                "id": seg.id,
                "type": seg.type,
                "start": seg.start,
                "end": seg.end,
                "duration": seg.duration,
                "script": seg.copy_text or f"{seg.label} 内容",
                "visual": seg.visual or f"{seg.label} 画面",
                "asset_id": seg.assetId if seg.assetId in asset_ids else None,
                "subtitle_style": "白字黑边",
                "transition": "硬切",
                "locked": False,
                "source": source,
            })

        source_counts: dict[str, int] = {}
        for s in segments:
            source_counts[s["source"]] = source_counts.get(s["source"], 0) + 1
        summary = ", ".join(f"{v}×{k}" for k, v in source_counts.items())

        return FinalScript.model_validate({
            "version": style,
            "total_duration": structure.meta.duration,
            "segments": segments,
            "metadata": {
                "restructure_needed": False,
                "edit_reason": "LLM不可用时使用模板结构",
                "warnings": [*base_warnings,
                    f"AI服务暂时不可用，已使用基础模板。素材分布: {summary}",
                    "上传素材后可在编辑页面使用「修复缺口」自动匹配和重组"],
            },
        })
    except Exception:
        return None


def _normalize_script(
    script: FinalScript,
    structure: VideoStructure,
    assets: list[dict[str, Any]],
    base_warnings: list[str],
) -> FinalScript:
    structure_duration = float(structure.meta.duration or sum(segment.duration for segment in structure.script))
    if structure_duration > 0:
        delta = abs(script.total_duration - structure_duration) / structure_duration
        if delta > 0.50:
            # LLM likely returned a flat segment that was auto-wrapped — total_duration
            # is meaningless. Use the structure duration instead.
            import sys
            sys.stderr.write(f"[MIGRATE] total_duration mismatch ({script.total_duration:.1f}s vs {structure_duration:.1f}s, {delta*100:.0f}%), using structure duration\n")
            sys.stderr.flush()
            payload = script.model_dump(mode="json")
            payload["total_duration"] = structure_duration
            script = FinalScript.model_validate(payload)
        elif delta > 0.25:
            raise ValueError(f"FinalScript total_duration ({script.total_duration:.1f}s) differs from structure ({structure_duration:.1f}s) by {delta*100:.0f}% (max 25%)")

    asset_by_id = {asset["id"]: asset for asset in assets}
    baseline_positions = {segment.id: index for index, segment in enumerate(structure.script)}

    # ── Determine user asset IDs (exclude reference video) ──
    user_asset_ids: set[str] = {
        a["id"] for a in assets
        if a.get("file_path") and not (a.get("analysis") or {}).get("reference_source")
    }

    # Exclude reference video — only user-uploaded assets should auto-bind
    bound_assets = {segment.id: segment.assetId for segment in structure.script
                    if segment.assetId in user_asset_ids}
    template_by_id = {segment.id: segment for segment in structure.script}
    payload = script.model_dump(mode="json")
    generated_segments = {segment["id"]: segment for segment in payload["segments"]}
    structure_ids = [segment.id for segment in structure.script]

    # ── Smart segment mapping: handle LLM returning mismatched segment counts ──
    if set(generated_segments) != set(structure_ids):
        import sys
        sys.stderr.write(
            f"[MIGRATE] Segment ID mismatch: generated={list(generated_segments.keys())[:3]}..., "
            f"expected={structure_ids[:3]}... → auto-mapping by position\n"
        )
        sys.stderr.flush()
        # Map LLM segments to structure by position, reusing LLM content as template
        llm_segments = list(payload["segments"])
        mapped = []
        for i, struct_id in enumerate(structure_ids):
            if i < len(llm_segments):
                # Use LLM segment content but override id/type from structure
                seg = dict(llm_segments[i])
                seg["id"] = struct_id
                seg["type"] = template_by_id[struct_id].type
                # Force-override source: only "original" if matched to a real user asset
                aid = seg.get("asset_id")
                seg["source"] = "original" if (aid and aid in user_asset_ids) else "aigc"
                seg.setdefault("subtitle_style", "白字黑边")
                seg.setdefault("transition", "硬切")
                seg.setdefault("locked", False)
                seg.setdefault("asset_id", None)
                seg.setdefault("camera", "静态")
                seg.setdefault("subtitle_anim", "淡入")
                seg.setdefault("pace", "正常")
                seg.setdefault("emotion", "亲切")
                seg.setdefault("visual_fx", "无")
                mapped.append(seg)
            else:
                # More structure segments than LLM returned → fill from template
                tmpl = template_by_id[struct_id]
                mapped.append({
                    "id": struct_id, "type": tmpl.type,
                    "start": tmpl.start, "end": tmpl.end, "duration": tmpl.duration,
                    "script": tmpl.copy_text or f"{tmpl.label} 内容",
                    "visual": tmpl.visual or f"{tmpl.label} 画面",
                    "source": "original" if (tmpl.assetId and tmpl.assetId in user_asset_ids) else "aigc",
                    "subtitle_style": "白字黑边",
                    "transition": "硬切", "locked": False, "asset_id": tmpl.assetId if (tmpl.assetId and tmpl.assetId in user_asset_ids) else None,
                    "camera": "静态", "subtitle_anim": "淡入",
                    "pace": "正常", "emotion": "亲切", "visual_fx": "无",
                })
        payload["segments"] = mapped
        # ── Quality gate: replace filler/short segments with template content ──
        for seg in payload["segments"]:
            script_text = str(seg.get("script", "")).strip()
            if len(script_text) < 5:
                tmpl = template_by_id.get(seg["id"])
                if tmpl:
                    seg["script"] = tmpl.copy_text or f"{tmpl.label} 内容"
                    seg["visual"] = tmpl.visual or f"{tmpl.label} 画面"
            seg["duration"] = max(float(seg.get("duration", 2.0)), 1.5)
        base_warnings.append(f"LLM返回{len(llm_segments)}个分镜，已自动映射到结构的{len(structure_ids)}个分镜")
        generated_segments = {segment["id"]: segment for segment in payload["segments"]}
    restructure_applied = _ai_requests_restructure(payload.get("metadata"))
    if not restructure_applied:
        payload["segments"] = [generated_segments[segment_id] for segment_id in structure_ids]
    warnings = list(base_warnings)
    for segment in payload["segments"]:
        template_segment = template_by_id[segment["id"]]
        segment["type"] = template_segment.type
        # Force-override source based on actual asset match (not LLM's guess)
        aid = segment.get("asset_id")
        segment["source"] = "original" if (aid and aid in user_asset_ids) else "aigc"
        if not restructure_applied:
            # Preserve original durations but allow LLM to optimize product/CTA timing
            seg_type = segment.get("type", "")
            llm_duration = float(segment.get("duration", template_segment.duration))
            if seg_type == "product" and llm_duration != template_segment.duration:
                # Allow product segment to be moved earlier (shorter → earlier exposure)
                if 1.0 <= llm_duration <= template_segment.duration * 1.5:
                    segment["duration"] = llm_duration
                else:
                    segment["duration"] = template_segment.duration
            elif seg_type == "cta" and llm_duration <= 4.0:
                # Allow CTA to be shortened to ≤4s (industry best practice)
                segment["duration"] = min(llm_duration, 4.0)
            else:
                segment["duration"] = template_segment.duration
        asset_id = bound_assets.get(segment["id"]) or segment.get("asset_id")
        segment["asset_id"] = asset_id
        if asset_id and asset_id not in asset_by_id:
            warnings.append(f"asset_id {asset_id} 不存在，已置为空")
            segment["asset_id"] = None
            asset_id = None
        if asset_id and _is_reference_asset(asset_by_id[asset_id]):
            segment["source_start"] = template_segment.start
            segment["source_end"] = template_segment.end
        else:
            segment["source_start"] = None
            segment["source_end"] = None
        # ── Backward compat: extract 5-params from script if new fields are empty ──
        _extract_params_from_script(segment)
        # ── Enforce per-type defaults when LLM returns generic "静态" ──
        _apply_type_defaults(segment)

    payload["total_duration"] = _reflow_output_timeline(payload["segments"])
    if structure_duration > 0 and abs(payload["total_duration"] - structure_duration) / structure_duration > 0.25:
        raise ValueError(f"Applied duration ({payload['total_duration']:.1f}s) differs from structure ({structure_duration:.1f}s) by >25%")

    for index, segment in enumerate(payload["segments"]):
        asset_id = segment.get("asset_id")
        if asset_id:
            asset = asset_by_id[asset_id]
            # Reference video assets should NOT be treated as user content
            if _is_reference_asset(asset):
                segment["source"] = "aigc"
            else:
                origin = asset.get("origin") or "uploaded"
                if origin == "uploaded":
                    segment["source"] = "reorder" if baseline_positions.get(segment["id"]) != index else "original"
                else:
                    segment["source"] = origin
        else:
            segment["source"] = "aigc"

    metadata = dict(payload.get("metadata") or {})
    existing_warnings = metadata.get("warnings") or []
    if isinstance(existing_warnings, list):
        warnings = [*existing_warnings, *warnings]
    metadata["restructure_needed"] = restructure_applied
    if not restructure_applied:
        metadata.pop("edit_plan", None)
        metadata["edit_reason"] = "未收到明确的结构重排建议，已保持样例段落顺序与时长。"
    metadata["warnings"] = warnings
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    payload["metadata"] = metadata
    return FinalScript.model_validate(payload)


def _is_reference_asset(asset: dict[str, Any]) -> bool:
    return (asset.get("analysis") or {}).get("reference_source") is True


def _ai_requests_restructure(metadata: Any) -> bool:
    """Determine if AI explicitly requested structural recut.

    Accepts: restructure_needed=true with a non-empty edit_reason.
    Also accepts: any explicit edit_plan (the AI wants to reorder).
    """
    if not isinstance(metadata, dict):
        return False
    if metadata.get("restructure_needed") is True:
        return bool(str(metadata.get("edit_reason") or "").strip())
    # Also check: if edit_plan is non-empty, the AI has specific reordering in mind.
    edit_plan = metadata.get("edit_plan", [])
    if isinstance(edit_plan, list) and len(edit_plan) > 0:
        return True
    return False


def _reflow_output_timeline(segments: list[dict[str, Any]]) -> float:
    cursor = 0.0
    for segment in segments:
        duration = round(max(float(segment["duration"]), 0.5), 3)
        segment["duration"] = duration
        segment["start"] = round(cursor, 3)
        cursor = round(cursor + duration, 3)
        segment["end"] = cursor
    return cursor


def _apply_type_defaults(segment: dict[str, Any]) -> None:
    """Enforce per-segment-type camera/emotion defaults when LLM returned generic values.

    The LLM prompt includes per-type suggestions but often defaults to '静态'/'亲切'.
    This post-processing ensures Hook/CTA use dynamic camera work.
    """
    seg_type = segment.get("type", "")
    current_camera = segment.get("camera", "静态")

    # Only override if the LLM returned the generic default
    if current_camera == "静态":
        TYPE_CAMERA: dict[str, str] = {
            "hook": "快推", "cta": "快推", "product": "缓推",
            "pain": "缓推", "proof": "横移",
        }
        if seg_type in TYPE_CAMERA:
            segment["camera"] = TYPE_CAMERA[seg_type]

    current_emotion = segment.get("emotion", "亲切")
    if current_emotion == "亲切":
        TYPE_EMOTION: dict[str, str] = {
            "hook": "惊讶", "cta": "紧迫", "proof": "权威",
        }
        if seg_type in TYPE_EMOTION:
            segment["emotion"] = TYPE_EMOTION[seg_type]


def _extract_params_from_script(segment: dict[str, Any]) -> None:
    """Extract 5 production params from script text into dedicated fields.

    Old format: "文案内容【镜】快推【字】弹入【速】快【情】惊讶【视】震屏"
    → script is cleaned, camera/subtitle_anim/pace/emotion/visual_fx are populated.
    Does nothing if new fields are already set.
    """
    import re
    script = segment.get("script", "")
    if not script:
        return

    # Only extract if new fields are still at default values
    existing_camera = segment.get("camera", "")
    if existing_camera and existing_camera != "静态":
        return  # Already has explicit params

    param_map = {
        "镜": ("camera", ["静态", "缓推", "快推", "拉远", "横移", "跟随", "手持微晃"]),
        "字": ("subtitle_anim", ["弹入", "淡入", "逐字出现", "缩放出现", "无动画"]),
        "速": ("pace", ["快", "正常", "慢"]),
        "情": ("emotion", ["惊讶", "紧迫", "亲切", "权威", "感动", "兴奋", "平静"]),
        "视": ("visual_fx", ["无", "震屏", "闪白", "慢动作", "放大", "模糊过渡"]),
    }

    for symbol, (field, valid_values) in param_map.items():
        pattern = rf"【{symbol}】([^\s【】]{{1,10}}(?:\([^)]*\))?)"
        m = re.search(pattern, script)
        if m:
            value = m.group(1).strip()
            # Normalize: remove speed suffixes like (1.3x)
            value = re.sub(r'\([^)]*\)', '', value).strip()
            if value in valid_values:
                segment[field] = value

    # Clean script text: remove all param markers
    cleaned = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', script)
    cleaned = re.sub(r'【[镜字速情视]】', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if cleaned:
        segment["script"] = cleaned
