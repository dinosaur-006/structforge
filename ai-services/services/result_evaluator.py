from __future__ import annotations

from typing import Any

from models.schemas import FinalScript, HealthScores, ResultEvaluation, ResultVersionOut, VideoStructure


VERSION_NAMES = {
    "default": "默认版",
    "high_click": "高点击版",
    "high_conversion": "高转化版",
    "fast_pace": "快节奏版",
    "high_quality": "高质感版",
}


class ResultEvaluator:
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
                    "visible": segment.source in {"original", "reorder", "packaging", "aigc", "recompose"},
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
                    "label": segment.label,
                    "start": segment.start,
                    "end": segment.end,
                    "source": "original",
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
                    "label": segment.script,
                    "start": segment.start,
                    "end": segment.end,
                    "source": segment.source,
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
        hook_score = _bounded(
            (35 if hook and segments and hook["id"] == segments[0]["id"] else 0)
            + (35 if hook and float(hook["end"]) <= 3 else 0)
            + (30 if hook and hook["visible"] else 0)
        )
        product_time = float(product["start"]) if product else None
        product_score = _bounded(100 - ((product_time or duration) / max(duration, 1)) * 100) if product else 0
        proof_text = str(proof["text"]).lower() if proof else ""
        proof_score = _bounded(
            (35 if proof else 0)
            + (35 if proof and proof["visible"] else 0)
            + (30 if any(word in proof_text for word in ("证明", "对比", "数据", "实测", "proof")) else 0)
        )
        average_duration = sum(float(segment["duration"]) for segment in segments) / max(len(segments), 1)
        pacing_score = _bounded(100 - max(0.0, average_duration - 5.5) * 10 - (100 - material_coverage) * 0.35)
        cta_score = _bounded(
            (35 if cta and segments and cta["id"] == segments[-1]["id"] else 0)
            + (30 if cta and float(cta["duration"]) >= 3 else 0)
            + (35 if cta and cta["visible"] else 0)
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


def _percentage_value(value: float) -> str:
    return f"{value:.0f}%"


def _seconds_value(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}s"
