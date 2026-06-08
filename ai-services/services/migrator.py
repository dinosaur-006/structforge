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
from services.transition_advisor import TransitionAdvisor
from services.content_safety import ContentSafetyService
from services.overlay_advisor import OverlayAdvisor


STYLE_INSTRUCTIONS: dict[str, str] = {
    "default": "保持原结构节奏，输出清晰、专业、可直接执行的分镜脚本。",
    "high_click": "强化前三秒冲突和停留理由，Hook 文案更短、更尖锐，字幕更醒目。",
    "high_conversion": "强化信任背书、优惠理由和 CTA 紧迫感，结尾转化动作更明确。",
    "fast_pace": "整体文案更短，镜头节奏更快，转场更紧凑，但总时长仍需匹配结构。",
    "high_quality": "文案更精致克制，画面描述增加光影、材质和高级感，转场更平滑。",
    "xiaohongshu_ces": """小红书 CES 算法优化版。算法权重：关注8分>评论/转发4分>点赞/收藏1分。
强制要求：正文总文案量需达600字以上。Hook和Pain段必须使用"争议性提问"拉动评论互动（如"原来这种护肤方式真的是智商税吗？"）。
CTA段必须加入互动引导（如"评论区告诉我你的肤质，我帮你选"）或抽奖福利话术。整体调性偏向精致生活美学。""",
    "wechat_social": """微信视频号社交裂变版。视频号极度依赖"朋友♡"社交分发链。
强制要求：在Proof或CTA段挂载高价值的"社交资产卡片"——可以是行业避坑指南、全网价格对比清单、或知识思维导图。
文案中需植入"转发给XX朋友"的社交裂变引导语。整体调性偏向真实可靠、有干货密度，让用户产生"不转就亏了"的冲动。""",
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
        self.client = client or DoubaoSeedClient(self.settings)
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
        prompt_context = {
            "project": {
                "id": project["id"],
                "name": project["name"],
                "product_info": product_info,
            },
            "style": style,
            "style_instruction": STYLE_INSTRUCTIONS[style],
            "structure": structure.model_dump(mode="json", by_alias=True),
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

        # Post-process: enrich with transition recommendations.
        transition_advisor = TransitionAdvisor(
            llm_endpoint=self.settings.doubao_llm_endpoint,
            llm_api_key=self.settings.doubao_llm_api_key,
            llm_model=self.settings.doubao_llm_model,
        )
        seg_dicts = [s.model_dump(mode="json") for s in script.segments]
        trans_recs = transition_advisor.recommend_for_script(seg_dicts)
        for seg in script.segments:
            if seg.id in trans_recs and trans_recs[seg.id]:
                best = trans_recs[seg.id][0]
                if not seg.transition or seg.transition == "硬切":
                    seg.transition = best["transition"]

        # Enrich with overlay recommendations.
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

        # Attach structured LLM qualitative review to script metadata.
        # Use rule-based baseline evaluation scores (same engine as the page display),
        # NOT the LLM analysis health scores, so numbers are consistent.
        baseline_eval = self.evaluator.evaluate_baseline(structure)
        review = self.evaluator.qualitative_review(script, before_scores={
            "hook_strength": baseline_eval.health.hook_strength,
            "selling_point_proof": baseline_eval.health.selling_point_proof,
            "cta_persuasiveness": baseline_eval.health.cta_persuasiveness,
        })
        if review:
            existing_meta = dict(script.metadata or {})
            existing_meta["ai_review"] = review
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
        errors: list[str] = []
        max_attempts = self.settings.llm_max_attempts
        for attempt in range(1, max_attempts + 1):
            try:
                prompt = _build_prompt(prompt_context, attempt)
                raw_payload = self.client.complete_json(prompt)
                if isinstance(raw_payload, str):
                    raw_payload = json.loads(raw_payload)
                script = FinalScript.model_validate(raw_payload)
                if script.version != style:
                    payload = script.model_dump(mode="json")
                    payload["version"] = style
                    script = FinalScript.model_validate(payload)
                return _normalize_script(script, structure, assets, base_warnings)
            except (json.JSONDecodeError, ValidationError, ValueError, StructureExtractionError) as exc:
                errors.append(str(exc))

        # Graceful degradation: if all LLM attempts fail, build a fallback script
        # with the structure template and product info, so user can still proceed.
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
    return f"""
你是 StructForge 的首席视频脚本导演，你的任务是将爆款样例视频的**结构骨架和创作方法**迁移到新产品上，生成一条比原视频**更具爆款潜力**的新脚本。

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

## 分镜类型详解

### Hook（开头吸引，3-5秒）
- **目标**: 0.3秒内让用户停下划动的手指
- **手法**: 认知冲突/反常识/悬念/强烈的视觉冲击
- **文案风格**: 短促有力，一句制造好奇。"等等...这不可能"、"他们不想让你知道这个"、"我测了47款，只有它..."
- **制作建议**: camera=快推, subtitle_anim=弹入, pace=快, emotion=惊讶/紧迫, visual_fx=震屏
- **致命错误**: 以品牌Logo开头、慢镜头、问候语

### Pain（痛点放大，3-5秒）
- **目标**: 让用户对号入座，产生"这就是我的问题"
- **手法**: 具体场景描述、身体感受、情绪共鸣
- **文案风格**: 第一人称或第二人称，描述一个具体的、熟悉的不便场景
- **制作建议**: camera=缓推/横移, subtitle_anim=淡入, pace=正常, emotion=亲切/共鸣
- **致命错误**: 泛泛而谈、说教、统计数据开场

### Product（产品引入，4-8秒）
- **目标**: 产品作为痛点的自然解决方案出现
- **硬性约束: product段的start时间必须≤5秒**（平台数据显示产品首次露出>5秒则转化率暴跌）
- **手法**: 英雄镜头展示、使用场景、质感特写
- **文案风格**: 具体、可感知的产品特性，避免空洞形容词
- **制作建议**: camera=缓推/拉远, subtitle_anim=缩放出现, pace=正常, emotion=兴奋/亲切, visual_fx=放大
- **致命错误**: 罗列参数、说"高品质""行业领先"、没有视觉冲击力

### Proof（卖点证明，5-8秒）
- **目标**: 用无可辩驳的证据摧毁购买疑虑
- **手法**: 对比演示、数据可视化、实测镜头、用户证言
- **文案风格**: 具体的数字、对比结果、可验证的声明。"用分贝仪实测"、"左vs右对比"、"7天前后"
- **制作建议**: camera=横移/静态, subtitle_anim=逐字出现, pace=正常, emotion=权威/兴奋, visual_fx=慢动作
- **致命错误**: 纯断言无证据、"你一定会喜欢"、没有具体数据

### CTA（转化号召，3-4秒）
- **目标**: 创造立即行动的紧迫感
- **硬性约束: CTA段 duration 必须≤4秒**（行业数据：>4秒的CTA转化率断崖下跌）
- **手法**: 具体的行动指令+稀缺性+零风险承诺+情感共鸣
- **文案风格**: 短句连续轰炸，层层递进。"只剩XX单"、"点击下方"、"不满意全额退"、"别让你的XX继续XX"
- **制作建议**: camera=快推, subtitle_anim=缩放出现, pace=快, emotion=紧迫/兴奋, visual_fx=放大/震屏
- **致命错误**: 模糊的"快来买吧"、没有紧迫感、没有具体指令、**时长超过4秒**

## 原视频健康度诊断

原视频评分（0-100，95%的视频综合分<65，75+已是专业水平）：
- 开头吸引力: {payload.get('original_scores', {}).get('hook_strength', '?')}
- 产品露出时机: {payload.get('original_scores', {}).get('product_exposure_timing', '?')}
- 卖点证明力: {payload.get('original_scores', {}).get('selling_point_proof', '?')}
- 节奏紧凑度: {payload.get('original_scores', {}).get('pacing_compactness', '?')}
- 转化号召力: {payload.get('original_scores', {}).get('cta_persuasiveness', '?')}
- 综合: {payload.get('original_scores', {}).get('overall', '?')}

最薄弱维度: {json.dumps(payload.get('original_scores', {}).get('weakest_dimensions', []), ensure_ascii=False)}

**你必须重点强化这两个薄弱维度。** 原视频在某项得分低，你的脚本必须在该维度使用更强的制作手法和更精准的文案。

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
    "emotional_resonance": "情绪共鸣（高能炸裂/温馨治愈/紧迫焦虑/精致共鸣/干货信赖/专业亲切）"
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

输入上下文：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def _build_fallback_script(
    structure: VideoStructure,
    assets: list[dict[str, Any]],
    style: str,
    base_warnings: list[str],
) -> FinalScript | None:
    """Build a basic script from the structure template when LLM is unavailable."""
    try:
        asset_ids = [a["id"] for a in assets]
        segments = []
        for seg in structure.script:
            segments.append({
                "id": seg.id,
                "type": seg.type,
                "start": seg.start,
                "end": seg.end,
                "duration": seg.duration,
                "script": seg.copy_text or f"{seg.label} 内容",
                "visual": seg.visual or f"{seg.label} 画面",
                "asset_id": asset_ids[0] if asset_ids else None,
                "subtitle_style": "白字黑边",
                "transition": "硬切",
                "locked": False,
                "source": "original",
            })
        return FinalScript.model_validate({
            "version": style,
            "total_duration": structure.meta.duration,
            "segments": segments,
            "metadata": {
                "restructure_needed": False,
                "edit_reason": "LLM不可用时使用模板结构",
                "warnings": [*base_warnings, "AI服务暂时不可用，已使用基础模板生成脚本"],
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
        if delta > 0.10:
            raise ValueError("FinalScript total_duration differs from structure duration by more than 10%")

    asset_by_id = {asset["id"]: asset for asset in assets}
    baseline_positions = {segment.id: index for index, segment in enumerate(structure.script)}
    bound_assets = {segment.id: segment.assetId for segment in structure.script if segment.assetId in asset_by_id}
    template_by_id = {segment.id: segment for segment in structure.script}
    payload = script.model_dump(mode="json")
    generated_segments = {segment["id"]: segment for segment in payload["segments"]}
    structure_ids = [segment.id for segment in structure.script]
    if len(generated_segments) != len(payload["segments"]) or set(generated_segments) != set(structure_ids):
        raise ValueError("FinalScript segment ids must exactly match the current structure")
    restructure_applied = _ai_requests_restructure(payload.get("metadata"))
    if not restructure_applied:
        payload["segments"] = [generated_segments[segment_id] for segment_id in structure_ids]
    warnings = list(base_warnings)
    for segment in payload["segments"]:
        template_segment = template_by_id[segment["id"]]
        segment["type"] = template_segment.type
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

    payload["total_duration"] = _reflow_output_timeline(payload["segments"])
    if structure_duration > 0 and abs(payload["total_duration"] - structure_duration) / structure_duration > 0.10:
        raise ValueError("Applied FinalScript duration differs from structure duration by more than 10%")

    for index, segment in enumerate(payload["segments"]):
        asset_id = segment.get("asset_id")
        if asset_id:
            origin = asset_by_id[asset_id].get("origin") or "uploaded"
            if origin == "uploaded":
                segment["source"] = "reorder" if baseline_positions.get(segment["id"]) != index else "original"
            else:
                segment["source"] = origin
        else:
            segment["source"] = "packaging"
            warnings.append(f"segment {segment['id']} 无绑定素材，渲染将使用可见包装占位卡")

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
