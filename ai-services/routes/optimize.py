"""Optimization pipeline API endpoints — waveform, thumbnail, and blueprint previews."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from config import Settings
from models.repository import SQLiteRepository

log = logging.getLogger(__name__)


def build_optimize_router(
    repository: SQLiteRepository,
    settings: Settings | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/optimize", tags=["optimize"])
    _settings = settings or Settings()

    # ── CORS preflight handler for this router ──
    @router.options("/{rest:path}")
    async def _cors_preflight(rest: str) -> dict[str, str]:
        return {}  # CORSMiddleware on app handles headers

    @router.get("/{project_id}/waveform")
    async def get_waveform(project_id: str) -> dict[str, Any]:
        """Return audio waveform data for the project's reference video."""
        try:
            video_path = _resolve_video_path(repository, project_id)
            from services.waveform import get_waveform_data
            data = get_waveform_data(str(video_path), ffmpeg_path=_settings.ffmpeg_path)
            if data is None:
                return {"data": [], "duration": 0, "labels": []}
            return data
        except Exception as exc:
            log.warning("Waveform extraction failed for project %s: %s", project_id, exc)
            return {"data": [], "duration": 0, "labels": []}

    @router.get("/{project_id}/thumbnail")
    async def get_thumbnail(project_id: str, t: float = 0.0) -> dict[str, Any]:
        """Return a base64-encoded JPEG thumbnail at the given time offset."""
        import base64
        import subprocess
        import tempfile
        video_path = _resolve_video_path(repository, project_id)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                [_settings.ffmpeg_path, "-y", "-v", "error",
                 "-ss", f"{t:.2f}",
                 "-i", str(video_path),
                 "-vframes", "1", "-q:v", "3",
                 "-s", "320x569",
                 tmp_path],
                capture_output=True, timeout=15,
            )
            if Path(tmp_path).exists():
                b64 = base64.b64encode(Path(tmp_path).read_bytes()).decode()
                Path(tmp_path).unlink(missing_ok=True)
                return {"thumbnail": f"data:image/jpeg;base64,{b64}"}
        except Exception:
            pass
        Path(tmp_path).unlink(missing_ok=True)
        return {"thumbnail": None}

    @router.get("/{project_id}/blueprint-payloads")
    async def get_blueprint_payloads(project_id: str) -> dict[str, Any]:
        """Return blueprint payload previews for AIGC segments.

        When the AI video generation API is not configured, this endpoint
        returns the full API request payload that *would* be sent, along
        with cost estimates. Used by the frontend PayloadPreviewDrawer.
        """
        from models.schemas import FinalScript
        from services.blueprint_renderer import build_blueprint_payload

        # Check project exists
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get the FinalScript
        script_payload = repository.get_project_script(project_id)
        if script_payload is None:
            return {
                "project_id": project_id,
                "video_gen_available": bool(_settings.doubao_image_api_key),
                "payloads": [],
                "total_estimated_cost_usd": 0.0,
                "total_estimated_tokens": 0,
            }

        script = FinalScript.model_validate(script_payload)

        # Check video gen API availability
        video_gen_available = bool(_settings.doubao_image_api_key)

        payloads = []
        total_cost = 0.0
        total_tokens = 0

        for segment in script.segments:
            # Only include segments that would use AIGC (no asset, source is aigc or original without asset)
            is_aigc_candidate = (
                (segment.source == "aigc" or not segment.asset_id)
                and segment.type not in ("packaging",)
            )
            if not is_aigc_candidate:
                continue

            bp = build_blueprint_payload(segment, api_key_available=video_gen_available)
            payloads.append({
                "segment_id": bp.segment_id,
                "segment_type": bp.segment_type,
                "segment_label": bp.segment_label,
                "duration": bp.duration,
                "visual_prompt": bp.visual_prompt,
                "script_text": bp.script_text,
                "camera": bp.camera,
                "visual_fx": bp.visual_fx,
                "pace": bp.pace,
                "emotion": bp.emotion,
                "model": bp.model,
                "estimated_tokens": bp.estimated_tokens,
                "estimated_cost_usd": bp.estimated_cost_usd,
                "api_provider": bp.api_provider,
                "is_available": bp.is_available,
                "api_payload": bp.api_payload,
            })
            total_cost += bp.estimated_cost_usd
            total_tokens += bp.estimated_tokens

        return {
            "project_id": project_id,
            "video_gen_available": video_gen_available,
            "payloads": payloads,
            "total_estimated_cost_usd": round(total_cost, 2),
            "total_estimated_tokens": total_tokens,
        }

    return router


def _resolve_video_path(repository: SQLiteRepository, project_id: str) -> Path:
    """Walk the project's analysis jobs to find the most recent uploaded video."""
    project = repository.get_project(project_id)
    if project:
        # Try the project's reference job first
        ref_job_id = project.get("reference_job_id")
        if ref_job_id:
            ref_job = repository.get_job(ref_job_id)
            if ref_job and ref_job.get("source_path"):
                candidate = Path(ref_job["source_path"])
                if candidate.exists():
                    return candidate

        # Try any completed analysis job
        for sample in repository.list_analysis_samples(project_id):
            job = repository.get_job(sample.get("job_id", ""))
            if job and job.get("source_path"):
                candidate = Path(job["source_path"])
                if candidate.exists():
                    return candidate

    # Fallback: generate a 1-second black placeholder video
    return _ensure_placeholder_video()


_PLACEHOLDER_PATH: Path | None = None


def _ensure_placeholder_video() -> Path:
    """Create a 1-second black 1080x1920 placeholder video if it doesn't exist."""
    global _PLACEHOLDER_PATH
    if _PLACEHOLDER_PATH is not None and _PLACEHOLDER_PATH.exists():
        return _PLACEHOLDER_PATH

    import subprocess
    import tempfile

    out = Path(tempfile.gettempdir()) / "structforge_placeholder_black.mp4"
    if out.exists():
        _PLACEHOLDER_PATH = out
        return out

    ffmpeg = "ffmpeg"
    cmd = [
        ffmpeg, "-y", "-f", "lavfi",
        "-i", "color=c=black:s=1080x1920:d=1:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an", str(out),
    ]
    subprocess.run(cmd, capture_output=True, timeout=15)
    if out.exists():
        _PLACEHOLDER_PATH = out
    return out
