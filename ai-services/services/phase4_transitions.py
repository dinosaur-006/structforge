"""Phase 4: Audio-driven transitions with TTS-priority beat alignment + restraint rules."""

from __future__ import annotations

from typing import Any


class RhythmAnalyzer:
    """TTS-priority beat alignment for cut points."""

    def calculate_edit_points(
        self,
        segments: list[Any],
        tts_timestamps: dict[str, list[dict[str, Any]]],
        bgm_beats: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Calculate optimal cut points: TTS-tail priority, BPM secondary, fixed fallback.

        Returns list of {segment_id, start_s, end_s, cut_point_s, aligned_to_tts, aligned_to_bpm}
        """
        beats = bgm_beats or []
        cursor = 0.0
        points = []

        for seg in segments:
            tts_end = self._get_tts_tail(tts_timestamps.get(seg.id, []))
            ideal_cut = cursor + max(seg.target_duration, tts_end if tts_end > 0 else seg.target_duration)
            aligned_to_tts = False
            aligned_to_bpm = False

            # Try BPM alignment within ±0.15s
            if beats:
                for beat in beats:
                    if abs(beat - ideal_cut) <= 0.15:
                        ideal_cut = beat
                        aligned_to_bpm = True
                        break

            if tts_end > 0:
                aligned_to_tts = True

            dur = round(ideal_cut - cursor, 3)
            points.append({
                "segment_id": seg.id,
                "start_s": round(cursor, 3),
                "end_s": round(ideal_cut, 3),
                "duration_s": max(dur, 0.5),
                "aligned_to_tts": aligned_to_tts,
                "aligned_to_bpm": aligned_to_bpm,
            })
            cursor = ideal_cut

        return points

    def _get_tts_tail(self, timestamps: list[dict[str, Any]] | None) -> float:
        """Get the end time of the last word in TTS timestamps."""
        if not timestamps:
            return 0.0
        return float(timestamps[-1].get("end", 0.0))

    def detect_beats(self, bgm_path: str) -> list[float]:
        """Extract beat positions from BGM file using librosa."""
        try:
            import librosa
            y, sr = librosa.load(bgm_path, sr=22050)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            return [float(t) for t in librosa.frames_to_time(beat_frames, sr=sr)]
        except Exception:
            return []


def assign_transitions(
    segments: list[Any],
    special_count_limit: int = 2,
) -> list[dict[str, Any]]:
    """Assign transitions: 90% hard cut, special only for proof→compare and last→CTA."""
    transitions = []
    special_count = 0

    for i in range(len(segments) - 1):
        from_type = segments[i].type.value if hasattr(segments[i].type, 'value') else str(segments[i].type)
        to_type = segments[i + 1].type.value if hasattr(segments[i + 1].type, 'value') else str(segments[i + 1].type)
        is_last_to_cta = (i == len(segments) - 2 and to_type == "cta")
        is_proof_to_compare = (from_type == "proof" and to_type == "compare")

        if is_proof_to_compare and special_count < special_count_limit:
            trans = "slide_left"
            special_count += 1
        elif is_last_to_cta and special_count < special_count_limit:
            trans = "zoom_in"
            special_count += 1
        else:
            trans = "dissolve"

        transitions.append({
            "from_id": segments[i].id,
            "to_id": segments[i + 1].id,
            "type": trans,
            "dissolve_s": 0.15 if trans == "dissolve" else 0.0,
            "special": trans in ("slide_left", "zoom_in"),
        })

    # Hard assertion: never exceed limit
    actual_special = sum(1 for t in transitions if t["special"])
    if actual_special > special_count_limit:
        # Downgrade excess specials to hard cut
        downgraded = 0
        for t in transitions:
            if t["special"] and actual_special - downgraded > special_count_limit:
                t["type"] = "hard_cut"
                t["dissolve_s"] = 0.0
                t["special"] = False
                downgraded += 1

    return transitions
