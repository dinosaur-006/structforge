"""Master pipeline orchestrating all 6 phases of video optimization v3."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from config import Settings
from services.optimization_models import (
    DecisionResult,
    DynamicStructure,
    EditOperation,
    EditPlan,
    ProductProfile,
    ProductType,
    PlatformType,
    RenderDecision,
    SegmentType,
    SellingPointNature,
    ShotPool,
    SubtitleEvent,
    SubtitleType,
    TransitionEvent,
    TransitionType,
)
from services.phase0_structure import StructureOptimizer, detect_subtitle_type
from services.phase1_multimodal import ShotAnalyzer

log = logging.getLogger(__name__)


class OptimizationPipeline:
    """Full video optimization pipeline v3.

    Usage:
        pipeline = OptimizationPipeline(settings)
        plan = pipeline.run(video_path="/path/to/original.mp4", product=ProductProfile(...))
        # plan.output_path contains the rendered video
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm_available = bool(settings.doubao_llm_endpoint and settings.doubao_llm_api_key)
        self._vision_available = bool(settings.doubao_vision_endpoint and settings.doubao_vision_api_key) or self._llm_available

    def run(
        self,
        video_path: str | Path,
        product: ProductProfile,
        *,
        bgm_path: str = "",
        lut_preset: str | None = None,
        protect_colors: bool = False,
    ) -> EditPlan:
        """Execute the full optimization pipeline.

        Args:
            video_path: Path to original sample video
            product: Product profile for structure generation
            bgm_path: Optional background music path
            lut_preset: LUT preset name (None = auto)
            protect_colors: Enable product color protection

        Returns:
            EditPlan with complete rendering instructions
        """
        t0 = time.monotonic()
        p = Path(video_path)

        # ── Phase 0: Dynamic Structure + Subtitle Detection ──
        log.info("Phase 0: Generating optimal structure...")
        optimizer = StructureOptimizer(
            llm_endpoint=self.settings.doubao_llm_endpoint or "",
            llm_api_key=self.settings.doubao_llm_api_key or "",
            llm_model=self.settings.doubao_llm_model,
        )
        structure = optimizer.generate(product)
        subtitle_type = detect_subtitle_type(
            str(p),
            vision_api_key=self.settings.doubao_llm_api_key or "",
            llm_endpoint=self.settings.doubao_llm_endpoint or "",
            llm_model=self.settings.doubao_llm_model,
        )
        log.info(f"Phase 0 done: {len(structure.segments)} segments, subtitle={subtitle_type.value}")

        # ── Phase 1: Multimodal Shot Understanding ──
        log.info("Phase 1: Analyzing shots...")
        analyzer = ShotAnalyzer(
            vision_endpoint=self.settings.doubao_llm_endpoint or "",
            vision_api_key=self.settings.doubao_llm_api_key or "",
            llm_model=self.settings.doubao_llm_model,
        )
        shots = analyzer.split_shots(str(p))
        shot_pool = analyzer.annotate(str(p), shots, settings=self.settings)
        log.info(f"Phase 1 done: {len(shot_pool.shots)} shots annotated")

        # ── Phase 2: Subtitle Generation ──
        log.info("Phase 2: Generating subtitles...")
        subtitles = self._generate_subtitles(structure, subtitle_type)
        log.info(f"Phase 2 done: {len(subtitles)} subtitle events")

        # ── Phase 3: Shot Matching & Recomposition ──
        log.info("Phase 3: Matching shots to structure...")
        decisions = self._match_shots(structure, shot_pool)
        log.info(f"Phase 3 done: {len(decisions)} decisions")

        # ── Phase 4: Transitions (TTS-priority beat alignment) ──
        log.info("Phase 4: Planning transitions...")
        transitions = self._plan_transitions(structure, decisions)
        log.info(f"Phase 4 done: {len(transitions)} transitions")

        # ── Phase 5: LUT Color ──
        active_lut = lut_preset or self._recommend_lut(shot_pool)
        log.info(f"Phase 5: LUT = {active_lut}, protect_colors = {protect_colors}")

        # ── Phase 6: AI Video Generation ──
        ai_count = sum(1 for d in decisions if d.decision == RenderDecision.AI_GENERATE)
        log.info(f"Phase 6: {ai_count} segments marked for AI generation")
        if ai_count > 0:
            self._warn_ai_triggers(decisions, structure, shot_pool)

        # ── Assemble EditPlan ──
        plan = EditPlan(
            product=product,
            structure=structure,
            shot_pool=shot_pool,
            decisions=decisions,
            transitions=transitions,
            subtitles=subtitles,
            bgm_path=bgm_path,
            output_path=str(self.settings.output_dir / f"{p.stem}_optimized.mp4"),
            special_transition_count=sum(1 for t in transitions if t.transition not in (TransitionType.HARD_CUT, TransitionType.DISSOLVE)),
        )

        if plan.special_transition_count > 2:
            log.warning(f"Special transition count {plan.special_transition_count} exceeds limit of 2!")

        log.info(f"Pipeline complete in {time.monotonic() - t0:.1f}s")
        return plan

    # ── Private helpers ──

    def _generate_subtitles(self, structure: DynamicStructure, subtitle_type: SubtitleType) -> list[SubtitleEvent]:
        """Generate screen subtitle events from structure segments."""
        events: list[SubtitleEvent] = []
        cursor = 0.0
        for seg in structure.segments:
            dur = seg.target_duration
            # Screen subtitle is the extracted keyword; TTS script is separate.
            text = seg.screen_subtitle or seg.label
            if text:
                events.append(SubtitleEvent(
                    segment_id=seg.id,
                    start_s=cursor,
                    end_s=cursor + dur,
                    text=text[:30],
                    position="bottom_center",
                    font_size=52 if seg.type.value == "hook" else 40,
                    effect="bounce_in" if seg.type.value == "hook" else "fade_in",
                ))
            cursor += dur
        return events

    def _match_shots(self, structure: DynamicStructure, shot_pool: ShotPool) -> list[DecisionResult]:
        """Match each structure segment to the best shot from the pool."""
        decisions: list[DecisionResult] = []
        for seg in structure.segments:
            best_score = 0.0
            best_shot_id: str | None = None
            evidence = ""

            for shot in shot_pool.shots:
                score = self._match_score(seg, shot)
                if score > best_score:
                    best_score = score
                    best_shot_id = shot.id
                    evidence = f"vision_tags={shot.vision.tags[:3]}"

            if best_score >= 60:
                decisions.append(DecisionResult(
                    segment_id=seg.id,
                    decision=RenderDecision.KEEP,
                    matched_shot_id=best_shot_id,
                    matched_score=round(best_score, 1),
                    operation=EditOperation(mute_original=True),
                    evidence=evidence,
                ))
            elif best_score >= 40:
                decisions.append(DecisionResult(
                    segment_id=seg.id,
                    decision=RenderDecision.RE_EDIT,
                    matched_shot_id=best_shot_id,
                    matched_score=round(best_score, 1),
                    operation=EditOperation(mute_original=True),
                    evidence=evidence,
                ))
            else:
                decisions.append(DecisionResult(
                    segment_id=seg.id,
                    decision=RenderDecision.AI_GENERATE,
                    matched_score=round(best_score, 1),
                    evidence="No matching shot in pool",
                ))

        return decisions

    def _match_score(self, seg: Any, shot: Any) -> float:
        """Compute multimodal match score between segment and shot."""
        score = 0.0
        # Type match — map English segment types to Chinese tag keywords
        type_cn_map = {
            "hook": ["冲突画面", "吸引注意", "开头", "hook"],
            "pain": ["痛点场景", "问题", "困境", "pain"],
            "product": ["产品特写", "产品展示", "卖点", "product"],
            "proof": ["证明", "对比", "数据", "proof"],
            "cta": ["行动号召", "购买", "链接", "cta"],
            "demo": ["演示", "使用场景", "效果", "demo"],
            "offer": ["优惠", "价格", "限时", "offer"],
            "compare": ["对比", "vs", "比较"],
            "scene": ["场景", "生活", "环境"],
            "tutorial": ["教程", "教学", "步骤"],
            "attract": ["吸引", "开头", "冲突画面"],
            "visual": ["展示", "外观", "颜值"],
            "lifestyle": ["生活", "场景", "氛围"],
            "problem": ["问题", "痛点", "困扰"],
            "price": ["价格", "省钱", "优惠"],
            "ingredients": ["配料", "成分", "原料"],
            "health": ["健康", "营养", "天然"],
            "taste": ["口感", "味道", "好吃"],
        }
        keywords = type_cn_map.get(seg.type.value if hasattr(seg.type, 'value') else str(seg.type), [seg.type.value])
        tags_str = " ".join(str(t).lower() for t in (shot.vision.tags or []))
        if any(kw.lower() in tags_str for kw in keywords):
            score += 30
        # Duration match
        dur_diff = abs(shot.duration_s - seg.target_duration) / max(seg.target_duration, 0.5)
        score += max(0, 15 - dur_diff * 15)
        # Quality
        if shot.quality.composition_score > 0.5:
            score += 10
        return min(score, 100.0)

    def _plan_transitions(self, structure: Any, decisions: list[DecisionResult]) -> list[TransitionEvent]:
        """Plan transitions with TTS-priority + 90% hard-cut rule."""
        transitions: list[TransitionEvent] = []
        cursor = 0.0
        special_count = 0
        for i in range(len(structure.segments) - 1):
            cursor += structure.segments[i].target_duration
            from_seg = structure.segments[i]
            to_seg = structure.segments[i + 1]

            # Default: hard cut
            trans = TransitionType.HARD_CUT
            dissolve = 0.0

            # Special transitions only for 2 specific cases
            is_proof_to_compare = (from_seg.type.value == "proof" and to_seg.type.value == "compare")
            is_last_to_cta = (i == len(structure.segments) - 2 and to_seg.type.value == "cta")

            if is_proof_to_compare and special_count < 2:
                trans = TransitionType.SLIDE_LEFT
                special_count += 1
            elif is_last_to_cta and special_count < 2:
                trans = TransitionType.ZOOM_IN
                special_count += 1
            else:
                # Use 0.15s dissolve for non-special transitions
                trans = TransitionType.DISSOLVE
                dissolve = 0.15

            transitions.append(TransitionEvent(
                from_segment_id=from_seg.id,
                to_segment_id=to_seg.id,
                transition=trans,
                dissolve_duration_s=dissolve,
                cue_time_s=round(cursor, 2),
            ))

        return transitions

    def _recommend_lut(self, shot_pool: ShotPool) -> str:
        """Recommend LUT based on dominant colors."""
        warm_count = 0
        cool_count = 0
        for shot in shot_pool.shots:
            colors = [c.lower() for c in shot.vision.dominant_colors]
            warm_count += sum(1 for c in colors if any(w in c for w in ("warm", "orange", "yellow", "red", "gold", "brown")))
            cool_count += sum(1 for c in colors if any(c2 in c for c2 in ("blue", "cool", "cyan", "teal", "green")))
        if warm_count > cool_count:
            return "电影质感"
        if cool_count > warm_count:
            return "清新明亮"
        return "自然通透"

    def _warn_ai_triggers(self, decisions: list[DecisionResult], structure: Any, shot_pool: ShotPool) -> None:
        """Log which segments triggered AI generation and why."""
        for d in decisions:
            if d.decision == RenderDecision.AI_GENERATE:
                seg = next((s for s in structure.segments if s.id == d.segment_id), None)
                name = seg.label if seg else d.segment_id
                log.warning(f"AI_GENERATE triggered for {name}: {d.evidence}")
