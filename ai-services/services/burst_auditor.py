"""Full-modal burst video audit engine.

Integrates 32 rule-based metrics with LLM soft analysis to produce
a comprehensive audit report and extractable viral creation templates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.burst_metrics import (
    BurstMetricsCalculator,
    DimensionReport,
    FullAuditReport,
    MetricResult,
)

log = logging.getLogger(__name__)

# ── LLM prompt for soft analysis ──

AUDIT_LLM_PROMPT = """你是资深电商短视频爆款策略专家。根据以下全模态数据，深度分析视频的爆款潜力。

## 数据
- ASR文本: {asr_text}
- 视觉标签: {vision_tags}
- OCR文字: {ocr_text}
- 镜头数: {shot_count}
- 时长: {duration}s

## 分析要求
1. 判断该视频最突出的爆款特征（1-2个维度）
2. 指出最明显的短板（1-2个维度）
3. 给出3条具体的、可操作的改进建议
4. 推测该视频的目标平台和品类

仅返回 JSON:
{{"top_strength":"最强维度名称","top_weakness":"最弱维度名称","suggestions":[{{"target":"指标名称","action":"具体改进措施","expected_effect":"预期效果(含数据)"}}],"platform_guess":"抖音/小红书/视频号","category_guess":"品类"}}
"""


class BurstAuditor:
    """Full-modal audit engine combining rule-based metrics + LLM analysis."""

    def __init__(
        self,
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        self._llm_endpoint = llm_endpoint
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_available = bool(llm_endpoint and llm_api_key)

    def audit(
        self,
        shots: list[dict[str, Any]],
        asr_text: str,
        asr_segments: list[dict[str, Any]],
        vision_frames: list[dict[str, Any]],
        duration: float,
        rhythm_points: list[dict[str, Any]] | None = None,
        packaging: dict[str, Any] | None = None,
        platform: str = "douyin",
    ) -> FullAuditReport:
        """Run full audit and return structured report with platform weights."""

        calc = BurstMetricsCalculator(
            shots=shots,
            asr_text=asr_text,
            asr_segments=asr_segments,
            vision_frames=vision_frames,
            duration=duration,
            rhythm_points=rhythm_points,
            packaging=packaging,
            platform=platform,
        )

        # Step 1: Calculate all 32 metrics
        all_metrics = calc.calculate_all()

        # Step 2: Aggregate into 5 dimension reports (platform-weighted)
        dimensions = calc.dimension_reports()

        # Step 3: Platform-weighted overall score
        platform_score = calc.platform_score()

        # Step 4: Generate auto-fix patches for critically low metrics
        auto_fix_patches = calc.generate_auto_fix_patches()

        # Step 5: LLM soft analysis (if available)
        llm_insights: dict[str, Any] = {}
        if self._llm_available:
            try:
                llm_insights = self._llm_analyze(calc, all_metrics)
            except Exception as exc:
                log.warning("LLM audit analysis failed: %s", exc)
                llm_insights = {"error": str(exc), "top_strength": "N/A", "top_weakness": "N/A"}

        # Step 6: Generate suggestions (merge auto-fix with LLM)
        suggestions = llm_insights.get("suggestions", [])
        if not suggestions:
            suggestions = self._rule_suggestions(dimensions)
        # Append auto-fix suggestions
        for fix in auto_fix_patches[:3]:
            suggestions.append({
                "target": fix["metric_name"],
                "action": fix["action"] + f" (自动修复)",
                "expected_effect": f"将 {fix['metric_id']} 从 {fix['current_score']} 分提升至达标线",
            })

        # Step 7: Extract burst template
        burst_template = calc.extract_burst_template()
        burst_template["platform"] = platform
        burst_template["platform_score"] = platform_score

        # Step 8: Unweighted overall for comparison
        overall = sum(d.score for d in dimensions) // max(len(dimensions), 1)

        return FullAuditReport(
            overall_score=overall,
            platform_score=platform_score,
            dimensions=dimensions,
            all_metrics=all_metrics,
            llm_insights=llm_insights,
            suggestions=suggestions,
            burst_template=burst_template,
            auto_fix_patches=auto_fix_patches,
        )

    def _llm_analyze(self, calc: BurstMetricsCalculator, metrics: list[MetricResult]) -> dict[str, Any]:
        """Invoke LLM for soft qualitative analysis via shared RobustLLMClient."""
        from services.llm_client import RobustLLMClient, LLMError

        vision_tags = []
        ocr_parts: list[str] = []
        for f in calc.vision_frames[:10]:
            vision_tags.extend(f.get("tags", []))
            ocr_parts.extend(f.get("ocr", []))

        prompt = AUDIT_LLM_PROMPT.format(
            asr_text=calc.asr_text[:500],
            vision_tags=", ".join(set(str(t) for t in vision_tags[:20])),
            ocr_text=" ".join(ocr_parts)[:300],
            shot_count=len(calc.shots),
            duration=calc.duration,
        )

        try:
            client = RobustLLMClient(self._llm_endpoint, self._llm_api_key, self._llm_model)
            result = client.complete_json(prompt, max_tokens=256)
            if isinstance(result, dict):
                return result
            if isinstance(result, str) and result.strip().startswith("{"):
                return json.loads(result.strip())
            return {"raw_response": str(result)}
        except LLMError as exc:
            log.warning("Audit LLM failed: %s", exc)
            return {"error": str(exc), "top_strength": "N/A", "top_weakness": "N/A"}

    def _rule_suggestions(self, dimensions: list[DimensionReport]) -> list[dict[str, str]]:
        """Generate rule-based suggestions when LLM is unavailable."""
        suggestions: list[dict[str, str]] = []
        for dim in dimensions:
            for w in dim.weaknesses[:1]:
                suggestions.append({
                    "target": w,
                    "action": f"强化{dim.name}维度的{w}指标",
                    "expected_effect": f"预计{dim.name}评分提升10-20分",
                })
        return suggestions[:5]

    def generate_structured_response(self, report: FullAuditReport) -> dict[str, Any]:
        """Convert report to frontend-friendly JSON."""
        return {
            "overall_score": report.overall_score,
            "platform_score": report.platform_score,
            "auto_fix_count": len(report.auto_fix_patches),
            "dimensions": [
                {
                    "name": dim.name,
                    "score": dim.score,
                    "strengths": dim.strengths,
                    "weaknesses": dim.weaknesses,
                    "metrics": [
                        {
                            "id": m.metric_id,
                            "name": m.name,
                            "score": m.score,
                            "evidence": m.evidence,
                            "raw_value": m.raw_value,
                            "passed": m.passed,
                        }
                        for m in dim.metrics
                    ],
                }
                for dim in report.dimensions
            ],
            "suggestions": report.suggestions,
            "llm_insights": report.llm_insights,
            "burst_template": report.burst_template,
        }
