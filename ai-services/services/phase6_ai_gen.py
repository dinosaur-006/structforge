"""Phase 6: AI video generation with precise trigger conditions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.optimization_models import ProductProfile, StructureSegment


def should_generate_with_ai(
    segment_type: str,
    match_score: float,
    segment_score: float,
    shot_quality: float,
    has_subtitle: bool,
    audio_quality: float,
) -> tuple[bool, str]:
    """Determine if AI video generation should be triggered.

    Returns (should_generate, reason).
    """
    # Trigger conditions (any one is enough)
    if match_score < 40:
        return True, f"match_score {match_score:.1f} < 40"
    if segment_score < 30:
        return True, f"segment_score {segment_score:.1f} < 30"
    if has_subtitle and match_score < 50:
        return True, "has hard subtitle and no alternative shot"
    if audio_quality < 0.2 and match_score < 40:
        return True, f"audio_quality {audio_quality:.1f} < 0.2 with poor match"

    # Skip conditions (any one is enough)
    if match_score > 60:
        return False, f"match_score {match_score:.1f} > 60"
    if segment_score > 50 and shot_quality > 0.6:
        return False, f"segment_score {segment_score:.1f} > 50 and shot_quality {shot_quality:.1f} > 0.6"

    return False, "no trigger condition met"


def generate_clip(
    target_segment: StructureSegment,
    product: ProductProfile,
    *,
    api_key: str,
    video_model: str,
    duration: int = 5,
    output_dir: str | Path = "outputs/ai_generated",
) -> str | None:
    """Generate a missing video clip via Seedance API."""
    import httpx
    import time

    if not api_key or not video_model:
        return None

    prompt = (
        f"竖屏短视频画面，9:16构图，{product.name}产品展示，"
        f"{target_segment.narrative_description or target_segment.tts_script[:60]}，"
        f"写实风格，高清，{target_segment.type.value}类画面，无字幕"
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target_segment.id}_ai_gen.mp4"

    try:
        # Create task
        resp = httpx.post(
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": video_model,
                "content": [{"type": "text", "text": prompt}],
                "duration": max(4, min(duration, 12)),
                "ratio": "9:16",
                "resolution": "720p",
                "watermark": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        task_id = resp.json().get("id", "")
        if not task_id:
            return None

        # Poll until complete
        for _ in range(30):
            time.sleep(3)
            qr = httpx.get(
                f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            qr.raise_for_status()
            payload = qr.json()
            if payload.get("status") == "succeeded":
                video_url = payload.get("content", {}).get("video_url", "") or payload.get("video_url", "")
                if video_url:
                    vr = httpx.get(video_url, timeout=60)
                    vr.raise_for_status()
                    out_path.write_bytes(vr.content)
                    return str(out_path)
                return None
            if payload.get("status") in ("failed", "expired"):
                return None
    except Exception:
        pass
    return None
