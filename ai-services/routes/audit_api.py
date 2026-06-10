"""Burst audit API endpoint — full-modal viral video analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import Settings
from models.repository import SQLiteRepository
from services.burst_auditor import BurstAuditor
from services.burst_metrics import FullAuditReport


class AuditResponse(BaseModel):
    overall_score: int
    dimensions: list[dict]
    suggestions: list[dict]
    llm_insights: dict
    burst_template: dict


def build_audit_router(
    repository: SQLiteRepository,
    settings: Settings | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
    _settings = settings or Settings()

    auditor = BurstAuditor(
        llm_endpoint=_settings.doubao_llm_endpoint,
        llm_api_key=_settings.doubao_llm_api_key,
        llm_model=_settings.doubao_llm_model,
    )

    @router.post("/{job_id}", response_model=AuditResponse)
    async def audit_video(job_id: str) -> dict:
        """Run full-modal burst audit on an analyzed video.

        Requires the analysis job to be completed with valid result data.
        """
        job = repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not yet completed")
        result = job.get("result") or {}
        if not result:
            raise HTTPException(status_code=400, detail="No analysis result available")

        # Extract data for metric calculation
        script = result.get("script", [])
        rhythm = result.get("rhythm", [])
        packaging = result.get("packaging", {})
        meta = result.get("meta", {})
        duration = float(meta.get("duration", 10))

        # Build shots from script segments
        shots = [
            {
                "start_s": float(s.get("start", 0)),
                "end_s": float(s.get("end", 0)),
                "duration_s": float(s.get("duration", s.get("end", 0)) - float(s.get("start", 0))),
                "type": s.get("type", ""),
            }
            for s in script
        ]

        # Get ASR from raw stored data (prefer _asr_data over result.asr)
        asr_raw = result.get("_asr_data", {}) or result.get("asr", {})
        asr_text = str(asr_raw.get("text", ""))
        asr_segments = asr_raw.get("segments", []) or []

        # Build vision frames from raw stored data when available
        # (_vision_frames has OCR, dominant_colors, product_type from pipeline)
        raw_frames: list[dict] = result.get("_vision_frames", [])
        vision_frames = []
        for i, s in enumerate(script):
            raw = raw_frames[i] if i < len(raw_frames) else {}
            vision_frames.append({
                "index": i + 1,
                "tags": list(raw.get("tags", [])) or s.get("visual_keywords", []) or [],
                "ocr": list(raw.get("ocr", [])),
                "description": s.get("visual", "") or raw.get("description", ""),
                "dominant_colors": list(raw.get("dominant_colors", [])),
                "product_type": raw.get("product_type", ""),
            })

        # Auto-detect platform from video resolution
        # Horizontal videos (width > height) are brand ads, not Douyin shorts
        resolution_str = str(meta.get("resolution", "1080x1920"))
        try:
            w, h = resolution_str.split("x")
            is_horizontal = int(w) > int(h)
        except (ValueError, TypeError):
            is_horizontal = False
        audit_platform = "default" if is_horizontal else "douyin"

        report = auditor.audit(
            shots=shots,
            asr_text=asr_text,
            asr_segments=asr_segments or [],
            vision_frames=vision_frames,
            duration=duration,
            rhythm_points=rhythm,
            packaging=packaging,
            platform=audit_platform,
        )

        return auditor.generate_structured_response(report)

    @router.get("/{job_id}/template")
    async def audit_template(job_id: str) -> dict:
        """Return only the burst template (creation parameters) for reuse."""
        job = repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        result = job.get("result") or {}
        if not result:
            raise HTTPException(status_code=400, detail="No analysis result available")

        script = result.get("script", [])
        meta = result.get("meta", {})
        asr_text = str(result.get("asr", {}).get("text", ""))

        from services.burst_metrics import BurstMetricsCalculator
        shots = [{"start_s": float(s.get("start", 0)), "duration_s": float(s.get("duration", 1))} for s in script]
        calc = BurstMetricsCalculator(
            shots=shots, asr_text=asr_text, asr_segments=[],
            vision_frames=[], duration=float(meta.get("duration", 10)),
        )
        return {"template": calc.extract_burst_template()}

    return router
