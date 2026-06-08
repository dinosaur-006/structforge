"""Intelligent highlight detection combining rhythm, vision, ASR, and LLM analysis."""

from __future__ import annotations

import json
from typing import Any

import httpx


HIGHLIGHT_PROMPT = """你是短视频高光片段识别助手。根据视频的时间线信息，找出最吸引观众的关键时刻。

视频总时长：{duration}秒

节奏点（second=秒, cuts=镜头切换次数, emotion=情绪强度 0-1）：
{rhythm_summary}

语音转写片段：
{asr_summary}

画面描述（按时间顺序）：
{vision_summary}

请找出 3-5 个最抓眼球、最适合做封面或预告的高光时刻。
返回 JSON 格式：{{"highlights":[{{"second": 秒数, "reason": "10字以内的中文理由"}}]}}
只返回 JSON，不要解释。"""


class HighlightDetector:
    """Fuses multiple signals to identify the most engaging moments in a video.

    Uses LLM for content-aware detection when available, with signal fusion as fallback.
    """

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

    def detect(
        self,
        rhythm_points: list[dict[str, Any]],
        asr_segments: list[dict[str, Any]] | None = None,
        vision_frames: list[dict[str, Any]] | None = None,
        duration: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Return a ranked list of highlight moments with reasons.

        Each result: {second, score, reason, is_peak}
        """
        # Try LLM-based detection first.
        if self._llm_available:
            llm_results = self._llm_detect(rhythm_points, asr_segments, vision_frames, duration)
            if llm_results:
                return llm_results

        # Fallback: signal fusion.
        return _signal_fusion_detect(rhythm_points, asr_segments, vision_frames)

    def _llm_detect(
        self,
        rhythm_points: list[dict[str, Any]],
        asr_segments: list[dict[str, Any]] | None,
        vision_frames: list[dict[str, Any]] | None,
        duration: float,
    ) -> list[dict[str, Any]] | None:
        """Use LLM to identify highlights from content understanding."""
        # Build compact summaries.
        rhythm_summary = "\n".join(
            f"  {p.get('second',0):.1f}s: cuts={p.get('cuts',0)}, emotion={p.get('emotion',0):.2f}"
            for p in rhythm_points[:15]
        )

        asr_lines: list[str] = []
        for seg in (asr_segments or [])[:20]:
            text = str(seg.get("text", ""))[:80]
            start = seg.get("start", 0)
            if text.strip():
                asr_lines.append(f"  {start:.1f}s: {text}")
        asr_summary = "\n".join(asr_lines) if asr_lines else "无语音转写"

        vision_lines: list[str] = []
        for frame in (vision_frames or [])[:10]:
            desc = str(frame.get("description", ""))[:100]
            idx = frame.get("index", "")
            if desc:
                vision_lines.append(f"  帧{idx}: {desc}")
        vision_summary = "\n".join(vision_lines) if vision_lines else "无画面描述"

        prompt = HIGHLIGHT_PROMPT.format(
            duration=f"{duration:.0f}",
            rhythm_summary=rhythm_summary,
            asr_summary=asr_summary,
            vision_summary=vision_summary,
        )
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            content = _extract_content(payload)
            if isinstance(content, str):
                content = json.loads(content)
            highlights = content.get("highlights", []) if isinstance(content, dict) else []
            results: list[dict[str, Any]] = []
            for h in highlights:
                second = float(h.get("second", 0))
                reason = str(h.get("reason", "高光时刻"))[:20]
                is_peak = bool(h.get("is_peak", True))
                # Estimate a score based on rank.
                rank = len(results) + 1
                score = max(40.0, 100.0 - rank * 12.0)
                results.append({
                    "second": second,
                    "score": score,
                    "reason": reason,
                    "is_peak": is_peak,
                })
            return sorted(results, key=lambda x: -x["score"])[:5]
        except Exception:
            return None


def _signal_fusion_detect(
    rhythm_points: list[dict[str, Any]],
    asr_segments: list[dict[str, Any]] | None,
    vision_frames: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Keyword and signal-based fallback highlight detection."""
    highlight_asr_keywords = [
        "惊艳", "绝了", "竟然", "太强", "只要", "免费",
        "限时", "独家", "最后", "必备", "神器",
        "新品", "首发", "爆款",
    ]
    highlight_vision_tags = ["冲突画面", "产品特写", "对比", "演示证明"]

    scores: list[dict[str, Any]] = []
    for point in rhythm_points:
        score = 0.0
        reasons: list[str] = []
        emotion = float(point.get("emotion", 0.0))
        cuts = int(point.get("cuts", 0))
        second = float(point.get("second", 0.0))

        if emotion >= 0.85:
            score += 35
            reasons.append(f"情绪峰值({emotion:.2f})")
        elif emotion >= 0.70:
            score += 20
        if cuts >= 6:
            score += 20
            reasons.append(f"高切换密度({cuts}次)")
        elif cuts >= 4:
            score += 10

        if asr_segments:
            asr_hits = 0
            for seg in asr_segments:
                seg_start = float(seg.get("start", 0))
                seg_end = float(seg.get("end", 0))
                if seg_start <= second <= seg_end or abs(seg_start - second) < 3:
                    text = str(seg.get("text", "")).lower()
                    for kw in highlight_asr_keywords:
                        if kw.lower() in text:
                            asr_hits += 1
                            break
            if asr_hits >= 2:
                score += 25
                reasons.append(f"语音关键词({asr_hits}个)")
            elif asr_hits == 1:
                score += 15

        if vision_frames:
            for frame in vision_frames:
                frame_tags = [str(t).strip() for t in frame.get("tags", [])]
                if any(t in highlight_vision_tags for t in frame_tags):
                    score += 10
                    reasons.append("视觉标签高亮")
                    break

        is_peak = bool(point.get("highlight")) or score >= 50
        scores.append({
            "second": second,
            "score": round(min(score, 100.0), 1),
            "reason": "; ".join(reasons) if reasons else "节奏标记",
            "is_peak": is_peak,
        })

    return sorted(scores, key=lambda x: -x["score"])[:5]


def _extract_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        return payload["choices"][0].get("message", {}).get("content", "")
    if "content" in payload:
        return payload["content"]
    return payload
