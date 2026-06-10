"""Deterministic segment reorder optimization.

Maximizes matched-asset coverage of critical positions (hook first, CTA last,
product early) while respecting locked segments.
"""

from __future__ import annotations

from typing import Any

from models.schemas import ScriptSegment, VideoStructure

NARRATIVE_ORDER: list[str] = ["hook", "pain", "product", "proof", "cta"]


class AutoReorderService:
    def reorder(self, structure: VideoStructure, asset_match_scores: dict[str, float]) -> tuple[VideoStructure, str]:
        """Return (reordered_structure, explanation).

        The asset_match_scores maps segment_id -> best available match score.
        Segments with higher scores are prioritized for critical positions.
        """
        segments = list(structure.script)
        locked_ids = {seg.id for seg in segments if seg.locked}
        unlocked = [seg for seg in segments if seg.id not in locked_ids]
        locked = [seg for seg in segments if seg.id in locked_ids]

        if len(unlocked) <= 1:
            return structure, "可重排的非锁定分镜不足，保持原顺序。"

        # Score each unlocked segment for each narrative position.
        position_weights = {
            "hook": 2.0,
            "cta": 2.0,
            "product": 1.5,
            "proof": 1.0,
            "pain": 1.0,
        }

        scored: list[dict[str, Any]] = []
        for seg in unlocked:
            best_score = 0.0
            for pos, weight in position_weights.items():
                pos_score = (asset_match_scores.get(seg.id, 0.0) / 100.0) * weight
                # Bonus for type matching: if segment.type == position
                if seg.type == pos:
                    pos_score += 0.3
                if pos_score > best_score:
                    best_score = pos_score
            scored.append({"segment": seg, "score": best_score})

        # Sort: higher score earlier, respecting narrative arc (hook-type first, cta-type last)
        def sort_key(item: dict[str, Any]) -> tuple[int, float]:
            seg = item["segment"]
            try:
                type_rank = NARRATIVE_ORDER.index(seg.type)
            except ValueError:
                type_rank = 2  # middle
            return (type_rank, -item["score"])

        sorted_unlocked = sorted(scored, key=sort_key)
        reordered_unlocked = [item["segment"] for item in sorted_unlocked]

        # Interleave locked segments at their original positions.
        orig_positions = {seg.id: idx for idx, seg in enumerate(segments)}
        locked_with_pos = [(seg, orig_positions[seg.id]) for seg in locked]
        locked_with_pos.sort(key=lambda x: x[1])

        result: list[ScriptSegment] = []
        unlocked_idx = 0
        for i in range(len(segments)):
            inserted = False
            for lseg, lpos in locked_with_pos:
                if lpos == i:
                    result.append(lseg)
                    inserted = True
                    break
            if not inserted and unlocked_idx < len(reordered_unlocked):
                result.append(reordered_unlocked[unlocked_idx])
                unlocked_idx += 1

        # If we still have leftover unlocked segments, append them.
        while unlocked_idx < len(reordered_unlocked):
            result.append(reordered_unlocked[unlocked_idx])
            unlocked_idx += 1

        # Build explanation.
        moved = [
            f"{seg.label}(原位置{orig_positions[seg.id] + 1}→新位置{new_idx + 1})"
            for new_idx, seg in enumerate(result)
            if seg.id not in locked_ids and new_idx != orig_positions.get(seg.id)
        ]
        if moved:
            explanation = f"已重排 {len(moved)} 个分镜以优化素材覆盖: {'; '.join(moved[:5])}"
        else:
            explanation = "素材已覆盖关键位置，保持原顺序。"

        reordered = structure.model_copy(update={"script": result})
        return reordered, explanation
