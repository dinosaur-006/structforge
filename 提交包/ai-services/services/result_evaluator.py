from __future__ import annotations

import json
import re
from typing import Any

import httpx

from models.schemas import FinalScript, HealthScores, ResultEvaluation, ResultVersionOut, VideoStructure


REVIEW_PROMPT = """你是 StructForge 的铁血总监兼资深运营专家。你的任务不是夸奖系统，而是挑刺。

优化前（样例基线）健康度：
- 开头吸引力: {hook_before}
- 卖点证明力: {proof_before}
- 转化号召力: {cta_before}

优化后脚本 + 渲染来源：
{script_summary}

## 核心审计死线：卡片穿帮率
统计 source='packaging' 的分镜数。如果 card_count >= 1：overall_score 严禁 >75！
在 remaining_issues 中严厉指出：第X分镜因[原因]严重降级为廉价卡片。

返回 JSON：
{{"improvements":[{{"point":"...","expected_effect":"..."}}],"remaining_issues":["..."],"overall_score":85,"card_count":0,"one_line_tip":"..."}}
只返回 JSON。"""


VERSION_NAMES = {
    "default": "默认版",
    "high_click": "高点击版",
    "high_conversion": "高转化版",
    "fast_pace": "快节奏版",
    "high_quality": "高质感版",
    "xiaohongshu_ces": "小红书CES破局版",
    "wechat_social": "微信视频号裂变版",
}


class ResultEvaluator:
    def __init__(
        self,
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        self._llm_available = bool(llm_endpoint and llm_api_key)
        self._endpoint = llm_endpoint
        self._api_key = llm_api_key
        self._model = llm_model

    def qualitative_review(self, script: FinalScript, before_scores: dict[str, int] | None = None) -> dict | None:
        """Return structured LLM review via shared RobustLLMClient."""
        if not self._llm_available:
            return None

        from services.llm_client import RobustLLMClient, LLMError

        script_summary = "\n".join(
            f"[{s.type}] {s.script[:60]}" for s in script.segments[:5]
        )
        before = before_scores or {}
        try:
            client = RobustLLMClient(self._endpoint, self._api_key, self._model)
            result = client.complete_json(
                REVIEW_PROMPT.format(
                    script_summary=script_summary,
                    hook_before=before.get("hook_strength", "?"),
                    proof_before=before.get("selling_point_proof", "?"),
                    cta_before=before.get("cta_persuasiveness", "?"),
                ),
                max_tokens=256,
            )
            if isinstance(result, dict):
                return result
            if isinstance(result, str) and result.strip().startswith("{"):
                return json.loads(_extract_json(result))
        except Exception:
            pass
        return None

    def evaluate_baseline(self, structure: VideoStructure) -> ResultEvaluation:
        return self._evaluate(
            [
                {
                    "id": segment.id,
                    "type": segment.type,
                    "start": segment.start,
                    "end": segment.end,
                    "duration": segment.duration,
                    "text": segment.copy_text,
                    "visible": True,
                }
                for segment in structure.script
            ]
        )

    def evaluate_script(self, script: FinalScript) -> ResultEvaluation:
        return self._evaluate(
            [
                {
                    "id": segment.id,
                    "type": segment.type,
                    "start": segment.start,
                    "end": segment.end,
                    "duration": segment.duration,
                    "text": segment.script,
                    # visible only when segment has a real user asset (not aigc/packaging)
                    "visible": (
                        segment.source == "original"
                        and segment.asset_id is not None
                    ),
                }
                for segment in script.segments
            ]
        )

    def baseline_version(self, structure: VideoStructure) -> ResultVersionOut:
        evaluation = self.evaluate_baseline(structure)
        return ResultVersionOut(
            id="original",
            name="样例基线",
            score=evaluation.health.overall,
            metrics=_comparison_metrics(evaluation, evaluation),
            health=evaluation.health,
            timeline=[
                {
                    "id": segment.id,
                    "label": _clean_label(segment.copy_text or segment.label),
                    "start": segment.start,
                    "end": segment.end,
                    "source": "original",
                    "subtitle": segment.copy_text or segment.label,
                    "script": (segment.copy_text or "")[:80],
                }
                for segment in structure.script
            ],
        )

    def script_version(
        self,
        script: FinalScript,
        baseline: ResultEvaluation,
        evaluation: ResultEvaluation | None = None,
    ) -> ResultVersionOut:
        current = evaluation or self.evaluate_script(script)
        return ResultVersionOut(
            id=script.version,
            name=VERSION_NAMES.get(script.version, script.version),
            score=current.health.overall,
            metrics=_comparison_metrics(baseline, current),
            health=current.health,
            timeline=[
                {
                    "id": segment.id,
                    "label": _clean_label(segment.script),
                    "start": segment.start,
                    "end": segment.end,
                    "source": segment.source,
                    "subtitle": _strip_params(segment.script),
                    "script": segment.script[:80],
                }
                for segment in script.segments
            ],
        )

    def _evaluate(self, segments: list[dict[str, Any]]) -> ResultEvaluation:
        duration = max((float(segment["end"]) for segment in segments), default=0.0)
        hook = next((segment for segment in segments if segment["type"] == "hook"), None)
        product = next((segment for segment in segments if segment["type"] == "product"), None)
        proof = next((segment for segment in segments if segment["type"] == "proof"), None)
        cta = next((segment for segment in segments if segment["type"] == "cta"), None)
        visible_count = sum(1 for segment in segments if segment["visible"])
        material_coverage = round(100 * visible_count / len(segments), 1) if segments else 0.0
        hook_text = str(hook.get("text", "")) if hook else ""
        hook_score = _bounded(
            (20 if hook and segments and hook["id"] == segments[0]["id"] else 0)
            + (15 if hook and float(hook["end"]) <= 2 else (10 if hook and float(hook["end"]) <= 3 else 0))
            + (15 if hook and hook["visible"] else 0)
            + (15 if len(hook_text) > 20 else (5 if len(hook_text) > 10 else 0))
            + (15 if _has_question_or_surprise(hook_text) else 0)
            + (10 if _has_emotional_trigger(hook_text) else 0)
            + (10 if _has_pattern_interrupt(hook_text) else 0)
        )

        product_time = float(product["start"]) if product else None
        product_score = _bounded(
            (30 if product_time is not None and product_time <= 5 else (15 if product_time is not None and product_time <= 8 else 0))
            + (25 if product and product["visible"] else 0)
            + (15 if product and len(str(product.get("text", ""))) > 20 else 0)
            + (15 if product and _has_solution_framing(str(product.get("text", ""))) else 0)
            + (15 if product_time is not None else 0)
        ) if product else 30

        proof_text = str(proof["text"]).lower() if proof else ""
        proof_score = _bounded(
            (20 if proof else 0)
            + (15 if proof and proof["visible"] else 0)
            + (20 if _has_specific_data(proof_text) else (10 if _has_numbers(proof_text) else 0))
            + (15 if len(proof_text) > 40 else (5 if len(proof_text) > 20 else 0))
            + (15 if proof and _has_comparison(proof_text) else 0)
            + (15 if proof and _has_credibility_signal(proof_text) else 0)
        )

        average_duration = sum(float(s["duration"]) for s in segments) / max(len(segments), 1)
        dur_variance = sum((float(s["duration"]) - average_duration) ** 2 for s in segments) / max(len(segments), 1)
        pacing_score = _bounded(
            85
            - max(0.0, average_duration - 5.5) * 8
            - (100 - material_coverage) * 0.25
            + (5 if dur_variance > 5 else 0)  # bonus for varied pacing
        )

        cta_text = str(cta.get("text", "")) if cta else ""
        cta_score = _bounded(
            (20 if cta and segments and cta["id"] == segments[-1]["id"] else 0)
            + (15 if cta and float(cta["duration"]) >= 3 else (8 if cta and float(cta["duration"]) >= 2 else 0))
            + (15 if cta and cta["visible"] else 0)
            + (15 if len(cta_text) > 20 else (5 if len(cta_text) > 10 else 0))
            + (15 if _has_urgency(cta_text) else 0)
            + (10 if _has_value_framing(cta_text) else 0)
            + (10 if _has_low_friction(cta_text) else 0)
        )
        health = HealthScores(
            hook_strength=hook_score,
            product_exposure_timing=product_score,
            selling_point_proof=proof_score,
            pacing_compactness=pacing_score,
            cta_persuasiveness=cta_score,
            overall=round((hook_score + product_score + proof_score + pacing_score + cta_score) / 5),
        )
        return ResultEvaluation(
            health=health,
            material_coverage=material_coverage,
            product_first_exposure=product_time,
            gap_count=len(segments) - visible_count,
            cta_duration=float(cta["duration"]) if cta else 0.0,
        )


def _bounded(value: float) -> int:
    return round(max(0, min(value, 100)))


def _has_question_or_surprise(text: str) -> bool:
    """Hook: Creates curiosity gap or shock."""
    return bool(re.search(r"[？！!?]|难道|竟然|居然|原来|天哪|震惊|没想到|揭秘|你以|你敢|你见过|从不", text))


def _has_emotional_trigger(text: str) -> bool:
    """Hook: Triggers emotional response (fear, desire, anger, FOMO)."""
    return bool(re.search(r"亏了|后悔|错过|千万别|别再|小心|注意|警惕|终于|太|绝了|炸了|疯了|赢麻", text))


def _has_pattern_interrupt(text: str) -> bool:
    """Hook: Breaks expected pattern — negative statement, contradiction, or metacommentary."""
    return bool(re.search(r"不要|别买|别急|等等|停|先别|不是|错了|假的|骗|真相|没人告诉|以为", text))


def _has_solution_framing(text: str) -> bool:
    """Product: Frames product as solution to specific problem."""
    return bool(re.search(r"解决|从此|不再|终于|有了它|帮你|让你|为你|搞定|省去|告别", text))


def _has_specific_data(text: str) -> bool:
    """Proof: Contains specific measurable data points (not just numbers)."""
    return bool(re.search(r"\d+\.?\d*\s*[%％]|\d+\s*[倍次天年月日元块千百万元亿]|\d+\s*[克斤升毫升度瓦]|实测|实验室|检测|认证|报告", text))


def _has_numbers(text: str) -> bool:
    """Proof: Contains any numbers."""
    return bool(re.search(r"\d+", text))


def _has_comparison(text: str) -> bool:
    """Proof: Uses comparison to establish superiority."""
    return bool(re.search(r"对比|相比|vs|比.*更|不如|远超|碾压|甩|吊打|秒杀|差距|区别|普通|传统|一般|别人|其他", text))


def _has_credibility_signal(text: str) -> bool:
    """Proof: Signals trustworthiness through credentials or transparency."""
    return bool(re.search(r"亲自|自己|用了|试了|测了|买了|花了|实拍|原相机|无滤镜|工厂|源头|研发|专利|认证|医生|专家|师傅|老师傅", text))


def _has_urgency(text: str) -> bool:
    """CTA: Creates time/quantity pressure."""
    return bool(re.search(r"限时|限量|最后|抢购|马上|立刻|现在|仅剩|错过|不再|即将|快|手慢|抓紧|库存|售罄|倒计时", text))


def _has_value_framing(text: str) -> bool:
    """CTA: Frames offer in terms of value/savings."""
    return bool(re.search(r"省[了]?\d|便宜|划算|值得|性价比|不到.*钱|只[要需].*[元块]|送|赠[品送]|白嫖|免费|包邮|补贴|优惠|折扣|降价", text))


def _has_low_friction(text: str) -> bool:
    """CTA: Reduces action friction — clear, simple next step."""
    return bool(re.search(r"点击|链接|主页|橱窗|小黄车|下单|购买|入手|冲|来吧|评论区|私信|直播间|头像|下方|左下|右下|点头像", text))


def _percentage_change(value: float) -> str:
    return f"{value:+.0f}%"


def _seconds_change(value: float) -> str:
    return f"{value:+.1f}s"


def _integer_change(value: int) -> str:
    return f"{value:+d}"


def _comparison_metrics(baseline: ResultEvaluation, current: ResultEvaluation) -> dict[str, Any]:
    exposure_delta = (current.product_first_exposure or 0) - (baseline.product_first_exposure or 0)
    return {
        "scoreDelta": current.health.overall - baseline.health.overall,
        "materialCoverage": {
            "before": _percentage_value(baseline.material_coverage),
            "after": _percentage_value(current.material_coverage),
            "delta": _percentage_change(current.material_coverage - baseline.material_coverage),
            "positive": current.material_coverage >= baseline.material_coverage,
        },
        "productExposure": {
            "before": _seconds_value(baseline.product_first_exposure),
            "after": _seconds_value(current.product_first_exposure),
            "delta": _seconds_change(exposure_delta),
            "positive": current.product_first_exposure is not None
            and (baseline.product_first_exposure is None or current.product_first_exposure <= baseline.product_first_exposure),
        },
        "gapCount": {
            "before": str(baseline.gap_count),
            "after": str(current.gap_count),
            "delta": _integer_change(current.gap_count - baseline.gap_count),
            "positive": current.gap_count <= baseline.gap_count,
        },
        "ctaDuration": {
            "before": _seconds_value(baseline.cta_duration),
            "after": _seconds_value(current.cta_duration),
            "delta": _seconds_change(current.cta_duration - baseline.cta_duration),
            "positive": current.cta_duration >= baseline.cta_duration,
        },
    }


def _clean_label(text: str) -> str:
    """Strip production params and truncate for timeline display."""
    if not text:
        return ""
    cleaned = _strip_params(text)
    return cleaned[:40] if len(cleaned) > 40 else cleaned


def _strip_params(text: str) -> str:
    """Remove 【镜】【字】【速】【情】【视】 params from text."""
    import re
    cleaned = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', text or '')
    cleaned = re.sub(r'【[镜字速情视]】', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or (text or '')


def _percentage_value(value: float) -> str:
    return f"{value:.0f}%"


def _seconds_value(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}s"
