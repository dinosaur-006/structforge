"""Optimization pipeline API endpoint — wires the 6-Phase pipeline into a live route."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Settings
from models.repository import SQLiteRepository
from services.optimization_models import PlatformType, ProductProfile, ProductType
from services.optimization_pipeline import OptimizationPipeline

log = logging.getLogger(__name__)


class OptimizeRequest(BaseModel):
    product_name: str = Field(min_length=1)
    product_type: str = "other"  # beauty / electronics / food / clothing / other
    selling_points: list[str] = Field(default_factory=list)
    target_audience: str = ""
    offer: str = ""
    tone: str = ""
    platform: str = "douyin"
    version: str = "standard"  # standard / high_click / high_conversion / fast_pace / high_quality


class OptimizeResponse(BaseModel):
    plan: dict[str, Any]
    success: bool


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

    @router.post("/{project_id}", response_model=OptimizeResponse)
    async def run_optimization(project_id: str, payload: OptimizeRequest) -> dict[str, Any]:
        """Execute the full 6-Phase optimization pipeline for a project."""
        # Validate project exists
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        # Resolve product type
        try:
            product_type = ProductType(payload.product_type)
        except ValueError:
            product_type = ProductType.OTHER

        # Resolve platform
        try:
            platform = PlatformType(payload.platform)
        except ValueError:
            platform = PlatformType.DOUYIN

        # Find a sample video path from the project's analysis jobs
        video_path = _resolve_video_path(repository, project_id)

        # Build product profile
        product = ProductProfile(
            name=payload.product_name,
            product_type=product_type,
            selling_points=payload.selling_points,
            target_audience=payload.target_audience,
            offer=payload.offer,
            tone=payload.tone or _default_tone(payload.product_type),
            platform=platform,
        )

        # Run the 6-phase pipeline
        try:
            pipeline = OptimizationPipeline(_settings)
            plan = pipeline.run(
                video_path=str(video_path),
                product=product,
            )
            return {"plan": plan.model_dump(), "success": True}
        except Exception as exc:
            log.exception("Optimization pipeline failed for project %s", project_id)
            raise HTTPException(status_code=500, detail=f"优化管道执行失败: {exc}") from exc

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


def _settings_or_default() -> Settings:
    try:
        return Settings()
    except Exception:
        return Settings(_env_file="")  # type: ignore[call-arg]


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


def _default_tone(product_type: str) -> str:
    defaults = {
        "beauty": "精致专业",
        "electronics": "科技感",
        "food": "诱人有食欲",
        "clothing": "时尚潮流",
    }
    return defaults.get(product_type, "专业可信")
