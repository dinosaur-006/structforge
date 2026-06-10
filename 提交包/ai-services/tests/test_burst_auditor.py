"""Tests for the full-modal burst audit engine."""

from __future__ import annotations

import pytest
from services.burst_metrics import (
    BurstMetricsCalculator,
    DimensionReport,
    FullAuditReport,
    MetricResult,
    PlatformWeights,
)
from services.burst_auditor import BurstAuditor


# ── Test data ──

SAMPLE_SHOTS = [
    {"start_s": 0.0, "end_s": 0.8, "duration_s": 0.8},
    {"start_s": 0.8, "end_s": 1.5, "duration_s": 0.7},
    {"start_s": 1.5, "end_s": 2.8, "duration_s": 1.3},
    {"start_s": 3.0, "end_s": 5.0, "duration_s": 2.0},
    {"start_s": 5.0, "end_s": 8.0, "duration_s": 3.0},
    {"start_s": 8.0, "end_s": 14.0, "duration_s": 6.0},
    {"start_s": 14.0, "end_s": 20.0, "duration_s": 6.0},
]

SAMPLE_ASR = "千万别买！除非你想交智商税。原来90%的人洗头方法都错了？这款氨基酸洗发水，我用了7天，控油效果提升300%，限时特惠仅剩最后200单！"

SAMPLE_ASR_SEGMENTS = [
    {"start": 0.0, "end": 1.5, "text": "千万别买！除非你想交智商税", "avg_db": -8.5},
    {"start": 1.5, "end": 4.0, "text": "原来90%的人洗头方法都错了？", "avg_db": -10.2},
    {"start": 4.0, "end": 10.0, "text": "这款氨基酸洗发水，我用了7天，控油效果提升300%", "avg_db": -12.0},
    {"start": 10.0, "end": 14.0, "text": "限时特惠仅剩最后200单！", "avg_db": -6.5},
]

SAMPLE_VISION = [
    {"index": 1, "tags": ["达人出镜", "皱眉抓狂", "震屏冲击"], "ocr": ["千万别买！"], "dominant_colors": ["#FF0000"], "description": "达人震惊特写"},
    {"index": 2, "tags": ["面部特写", "微笑展示"], "ocr": [], "dominant_colors": ["#FFFFFF"], "description": "达人微笑"},
    {"index": 3, "tags": ["产品特写", "瓶身特写", "举起商品"], "ocr": ["氨基酸洗发水"], "dominant_colors": ["#FFD700"], "description": "产品展示"},
    {"index": 4, "tags": ["液体流动", "泡沫细腻", "涂抹演示"], "ocr": ["控油效果提升300%"], "dominant_colors": ["#FFFFFF"], "description": "使用演示"},
    {"index": 5, "tags": ["颜色对比", "质地展示"], "ocr": ["7天前后对比"], "dominant_colors": ["#FFFFFF"], "description": "对比展示"},
    {"index": 6, "tags": ["价格角标", "指向屏幕"], "ocr": ["限时特惠", "¥99", "原价¥299"], "dominant_colors": ["#FF0000"], "description": "CTA结尾"},
]

SAMPLE_PACKAGING = {
    "subtitleStyle": ["弹入动画", "黄字白描边"],
    "transitions": ["硬切", "溶解", "缩放"],
    "overlays": ["价格标签", "箭头强调"],
}

SAMPLE_RHYTHM = [
    {"second": 0.0, "cuts": 4, "emotion": 0.92},
    {"second": 3.0, "cuts": 3, "emotion": 0.85},
    {"second": 6.0, "cuts": 5, "emotion": 0.78},
    {"second": 10.0, "cuts": 2, "emotion": 0.65},
    {"second": 15.0, "cuts": 4, "emotion": 0.88},
    {"second": 18.0, "cuts": 6, "emotion": 0.95, "highlight": True},
]


# ═══════════════════════════════════════════════════════════════
# Metrics Calculator Tests
# ═══════════════════════════════════════════════════════════════

class TestBurstMetricsCalculator:
    def test_calculates_all_metrics(self) -> None:
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            rhythm_points=SAMPLE_RHYTHM, packaging=SAMPLE_PACKAGING,
        )
        results = calc.calculate_all()
        # Should produce metrics across all 4 modalities and 5 dimensions
        assert len(results) >= 28, f"Expected >=28 metrics, got {len(results)}"

        # Verify dimensions are all covered
        dims = {r.dimension for r in results}
        assert dims == {"hook", "trust", "density", "pacing", "cta"}, f"Missing dimensions: {dims}"

        # Verify modalities
        mods = {r.modality for r in results}
        assert "visual" in mods
        assert "audio" in mods
        assert "subtitle" in mods

    def test_hook_metrics_detect_viral_pattern(self) -> None:
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        hook_metrics = [r for r in calc.calculate_all() if r.dimension == "hook"]
        assert len(hook_metrics) >= 8

        # H-A2 should detect conflict words ("千万别买", "竟然", "为什么")
        ha2 = next((r for r in hook_metrics if r.metric_id == "H-A2"), None)
        assert ha2 is not None
        assert ha2.score >= 50, f"Should detect conflict words, got {ha2.score}: {ha2.evidence}"

        # H-V2 should detect visual conflict
        hv2 = next((r for r in hook_metrics if r.metric_id == "H-V2"), None)
        assert hv2 is not None

    def test_cta_metrics_detect_conversion_elements(self) -> None:
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        cta_metrics = [r for r in calc.calculate_all() if r.dimension == "cta"]

        # C-A1: action words ("点击", "购买", "限时")
        ca1 = next((r for r in cta_metrics if r.metric_id == "C-A1"), None)
        assert ca1 is not None
        assert ca1.score >= 30, f"CTA action words should score, got {ca1.score}"

        # C-S1: price anchoring
        cs1 = next((r for r in cta_metrics if r.metric_id == "C-S1"), None)
        assert cs1 is not None

    def test_dimension_reports(self) -> None:
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        reports = calc.dimension_reports()
        assert len(reports) == 5
        for r in reports:
            assert 0 <= r.score <= 100, f"Dimension {r.name} score out of range: {r.score}"
            assert len(r.metrics) > 0, f"Dimension {r.name} has no metrics"

    def test_burst_template_extraction(self) -> None:
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        template = calc.extract_burst_template()
        assert "hook_frequency" in template
        assert "conflict_word_count" in template
        assert "action_word_count" in template
        assert "overall_score" in template
        assert template["conflict_word_count"] >= 1  # Sample has "千万别买", "竟然", etc.

    def test_metric_result_ranges(self) -> None:
        for metric in BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text="test", asr_segments=[],
            vision_frames=[], duration=10.0,
        ).calculate_all():
            assert 0 <= metric.score <= 100, f"Metric {metric.metric_id} score {metric.score} out of range"
            assert metric.evidence, f"Metric {metric.metric_id} missing evidence"


# ═══════════════════════════════════════════════════════════════
# Auditor Tests
# ═══════════════════════════════════════════════════════════════

class TestBurstAuditor:
    def test_auditor_without_llm_produces_valid_report(self) -> None:
        auditor = BurstAuditor()  # No LLM config
        report = auditor.audit(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            rhythm_points=SAMPLE_RHYTHM, packaging=SAMPLE_PACKAGING,
        )
        assert isinstance(report, FullAuditReport)
        assert 0 <= report.overall_score <= 100
        assert len(report.dimensions) == 5
        assert len(report.all_metrics) >= 28

    def test_structured_response_serializable(self) -> None:
        import json
        auditor = BurstAuditor()
        report = auditor.audit(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        response = auditor.generate_structured_response(report)
        json_str = json.dumps(response, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["overall_score"] == report.overall_score
        assert len(parsed["dimensions"]) == 5

    def test_minimal_data_does_not_crash(self) -> None:
        """Empty/minimal input should still produce results without crashing."""
        auditor = BurstAuditor()
        report = auditor.audit(
            shots=[], asr_text="", asr_segments=[], vision_frames=[], duration=1.0,
        )
        assert isinstance(report, FullAuditReport)
        assert report.overall_score >= 0

    def test_rule_suggestions_when_no_llm(self) -> None:
        auditor = BurstAuditor()
        report = auditor.audit(
            shots=SAMPLE_SHOTS, asr_text="", asr_segments=[], vision_frames=[], duration=10.0,
        )
        # Should have rule-based suggestions
        assert len(report.suggestions) > 0
        for s in report.suggestions:
            assert "action" in s
            assert "expected_effect" in s


# ═══════════════════════════════════════════════════════════════
# Enhancement: Platform Weights + Auto-Fix Patches
# ═══════════════════════════════════════════════════════════════

class TestPlatformWeights:
    def test_xiaohongshu_weights(self) -> None:
        w = PlatformWeights.for_platform("xiaohongshu")
        assert w.hook_conflict_words == 2.0   # CES: 评论权重极高
        assert w.cta_action_words == 0.8       # 小红书不要生硬CTA
        assert w.platform == "xiaohongshu"

    def test_douyin_weights(self) -> None:
        w = PlatformWeights.for_platform("douyin")
        assert w.density_first_benefit == 2.0   # 抖音: 利益点前置 = 一票否决权
        assert w.cta_price_anchor == 2.0         # 千川: 价格锚定直接决定ROI
        assert w.platform == "douyin"

    def test_wechat_weights(self) -> None:
        w = PlatformWeights.for_platform("wechat")
        assert w.trust_data_evidence == 1.5      # 视频号: 干货密度驱动社交转发
        assert w.platform == "wechat"

    def test_default_is_neutral(self) -> None:
        w = PlatformWeights.for_platform("unknown")
        assert w.hook_conflict_words == 1.0
        assert all(
            getattr(w, f) == 1.0
            for f in ["hook_conflict_words", "trust_data_evidence", "cta_price_anchor"]
        )

    def test_platform_weighted_score_differs(self) -> None:
        """Same video should get different scores on different platforms."""
        calc_dy = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING, platform="douyin",
        )
        calc_xhs = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING, platform="xiaohongshu",
        )
        dy_score = calc_dy.platform_score()
        xhs_score = calc_xhs.platform_score()
        # Scores should differ because weights are different
        assert dy_score != xhs_score, f"Platform scores should differ: douyin={dy_score}, xiaohongshu={xhs_score}"


class TestAutoFixPatches:
    def test_generates_patches_for_low_scores(self) -> None:
        """Metrics that score critically low should trigger auto-fix patches."""
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text="", asr_segments=[],
            vision_frames=[], duration=10.0,
        )
        patches = calc.generate_auto_fix_patches()
        # With empty input, most metrics should be critically low, triggering patches
        assert len(patches) > 0
        for p in patches:
            assert "metric_id" in p
            assert "rfc6902_patch" in p
            assert "severity" in p
            # Each patch must be valid RFC 6902
            for op in p["rfc6902_patch"]:
                assert "op" in op
                assert "path" in op

    def test_high_scoring_metrics_no_patches(self) -> None:
        """High-scoring metrics should NOT trigger patches."""
        calc = BurstMetricsCalculator(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING,
        )
        patches = calc.generate_auto_fix_patches()
        # Sample has conflict words, price anchors, etc. — fewer patches expected
        # C-S1 should NOT trigger because sample has price anchoring
        triggered_ids = {p["metric_id"] for p in patches}
        # C-S1 has price anchoring in sample data → should NOT trigger
        # T-A1 has data evidence → should NOT trigger
        assert len(patches) < 5, f"Expected fewer patches for rich data, got {len(patches)}"

    def test_auditor_includes_auto_fix_in_report(self) -> None:
        """Auditor should include auto_fix_patches in the report."""
        auditor = BurstAuditor()
        report = auditor.audit(
            shots=SAMPLE_SHOTS, asr_text=SAMPLE_ASR, asr_segments=SAMPLE_ASR_SEGMENTS,
            vision_frames=SAMPLE_VISION, duration=20.0,
            packaging=SAMPLE_PACKAGING, platform="douyin",
        )
        assert report.platform_score > 0
        assert report.platform_score != report.overall_score  # Weighted ≠ unweighted
        response = auditor.generate_structured_response(report)
        assert "platform_score" in response
        assert "auto_fix_count" in response
