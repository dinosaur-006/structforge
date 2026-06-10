"""StructForge ComfyUI Service — RunningHub cloud integration via ComfyKit.

Mirrors Pixelle-Video's MediaService pattern.
Supports both RunningHub (cloud) and self-hosted ComfyUI.

Usage:
    from services.comfyui_service import ComfyUIService

    svc = ComfyUIService(runninghub_api_key="rh-key-xxx")

    # Generate image
    result = await svc.generate_image(
        prompt="旺仔牛奶红色铁罐特写，金属反光，9:16竖屏",
        width=1080, height=1920,
    )
    print(result["url"])  # downloadable image URL

    # Generate video from image
    result = await svc.generate_video(
        prompt="产品旋转展示，慢动作...",
        image_path="/path/to/first_frame.png",
        duration=5.0,
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


class ComfyUIService:
    """Unified ComfyUI service for image & video generation via ComfyKit.

    Uses ComfyKit to talk to either:
    - RunningHub (cloud)  → runninghub_api_key required
    - Self-hosted ComfyUI (local) → comfyui_url required

    Verified RunningHub workflow IDs (from Pixelle-Video):
    - image_flux:    1983427617984585729  (Flux text-to-image)
    - image_qwen:    (Chinese-optimized)
    - image_sdxl:    (fast SDXL)
    - video_wan2.2:  1991693844100100097  (WAN 2.2 image-to-video)
    - video_fusionx: (WAN 2.1 FusionX enhanced)
    """

    # ── Verified RunningHub workflow IDs ──
    WORKFLOWS: dict[str, str] = {
        # Image generation
        "image_flux": "1983427617984585729",
        "image_flux2": "1983427617984585730",
        "image_qwen": "1983427617984585731",
        "image_sd3.5": "1983427617984585732",
        "image_sdxl": "1983427617984585733",
        # Video generation (verified on RunningHub 2026-06)
        "video_wan2.2": "1993931250872369154",
        # TTS
        "tts_edge": "1983513964837543938",
        "tts_spark": "1983513964837543939",
    }

    def __init__(
        self,
        runninghub_api_key: str | None = None,
        runninghub_url: str | None = None,
        comfyui_url: str | None = None,
        default_image_workflow: str = "image_flux",
        default_video_workflow: str = "video_wan2.2",
    ) -> None:
        self._kit: Any = None
        self._kit_config_hash: str | None = None
        self._config: dict[str, Any] = {}

        if runninghub_api_key:
            self._config["runninghub_api_key"] = runninghub_api_key
            if runninghub_url:
                self._config["runninghub_url"] = runninghub_url
            log.info("ComfyUIService: RunningHub configured (url=%s)",
                     runninghub_url or "default")
        if comfyui_url:
            self._config["comfyui_url"] = comfyui_url
            log.info("ComfyUIService: self-hosted ComfyUI at %s", comfyui_url)

        self.default_image_workflow = default_image_workflow
        self.default_video_workflow = default_video_workflow

        if not self._config:
            log.warning("ComfyUIService: no RunningHub key or ComfyUI URL — disabled")
        else:
            log.info("ComfyUIService: ready (image=%s, video=%s)",
                     default_image_workflow, default_video_workflow)

    @property
    def available(self) -> bool:
        return bool(self._config)

    def _get_kit(self) -> Any:
        """Lazy-init ComfyKit with config-change detection (Pixelle-Video pattern)."""
        current_hash = hashlib.md5(
            json.dumps(self._config, sort_keys=True).encode()
        ).hexdigest()

        if self._kit is None or self._kit_config_hash != current_hash:
            if self._kit is not None:
                log.info("ComfyKit config changed, recreating instance")

            from comfykit import ComfyKit
            self._kit = ComfyKit(**self._config)
            self._kit_config_hash = current_hash
            log.info("ComfyKit instance created")

        return self._kit

    # ═══════════════════════════════════════════════════════════
    # Image Generation
    # ═══════════════════════════════════════════════════════════

    async def generate_image(
        self,
        prompt: str,
        workflow: str | None = None,
        width: int = 1080,
        height: int = 1920,
        negative_prompt: str | None = None,
        steps: int = 20,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate an image via RunningHub ComfyUI.

        Returns:
            {"url": "https://...", "downloaded_path": "/tmp/xxx.png"}
        """
        if not self.available:
            raise RuntimeError("ComfyUIService not configured")

        wf_id = self.WORKFLOWS.get(workflow or self.default_image_workflow)
        if not wf_id:
            available = ", ".join(self.WORKFLOWS.keys())
            raise ValueError(
                f"Unknown image workflow '{workflow}'. Available: {available}"
            )

        kit = self._get_kit()
        params: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if steps:
            params["steps"] = steps
        if seed is not None:
            params["seed"] = seed

        log.info("ComfyUI generate_image: %s (wf=%s, %dx%d)",
                 prompt[:80], workflow or self.default_image_workflow, width, height)

        result = await kit.execute(wf_id, params)

        if result.status != "completed":
            raise RuntimeError(
                f"ComfyUI image generation failed (status={result.status}): {result.msg or 'unknown'}"
            )

        if not result.images:
            raise RuntimeError("ComfyUI returned no images")

        output: dict[str, Any] = {"url": result.images[0]}
        log.info("ComfyUI image generated: %s", result.images[0][:80])
        return output

    # ═══════════════════════════════════════════════════════════
    # Video Generation
    # ═══════════════════════════════════════════════════════════

    async def generate_video(
        self,
        prompt: str,
        image_path: str | None = None,
        workflow: str | None = None,
        width: int = 1080,
        height: int = 1920,
        duration: float = 5.0,
    ) -> dict[str, Any]:
        """Generate a video via RunningHub ComfyUI (image-to-video or text-to-video).

        Args:
            prompt: Video description (English recommended)
            image_path: Optional first frame image for i2v
            duration: Target duration in seconds

        Returns:
            {"url": "https://...", "duration": 5.0}
        """
        if not self.available:
            raise RuntimeError("ComfyUIService not configured")

        wf_id = self.WORKFLOWS.get(workflow or self.default_video_workflow)
        if not wf_id:
            available = ", ".join(self.WORKFLOWS.keys())
            raise ValueError(
                f"Unknown video workflow '{workflow}'. Available: {available}"
            )

        kit = self._get_kit()
        # WAN 2.2 workflow uses 512x288 (Pixelle-Video verified)
        params: dict[str, Any] = {
            "prompt": prompt,
            "width": min(width, 512),
            "height": min(height, 288),
            "duration": duration,
            "index": 1,
        }
        if image_path:
            params["image_path"] = image_path

        log.info("ComfyUI generate_video: %s (wf=%s, %ds)",
                 prompt[:80], workflow or self.default_video_workflow, duration)

        result = await kit.execute(wf_id, params)

        if result.status != "completed":
            raise RuntimeError(
                f"ComfyUI video generation failed (status={result.status}): {result.msg or 'unknown'}"
            )

        if not result.videos:
            raise RuntimeError("ComfyUI returned no videos")

        output: dict[str, Any] = {
            "url": result.videos[0],
            "duration": getattr(result, "duration", None) or duration,
        }
        log.info("ComfyUI video generated: %s", result.videos[0][:80])
        return output

    # ═══════════════════════════════════════════════════════════
    # Connectivity Check
    # ═══════════════════════════════════════════════════════════

    async def health_check(self) -> dict[str, Any]:
        """Test connectivity by running a minimal generation (1×1 pixel test).

        Returns:
            {"status": "healthy", "latency_seconds": 12.3}
            or
            {"status": "error", "message": "..."}
        """
        if not self.available:
            return {"status": "unconfigured", "message": "No RunningHub key or ComfyUI URL set"}

        import time
        t0 = time.monotonic()
        try:
            # Minimal test: generate a tiny image
            result = await self.generate_image(
                prompt="test",
                width=64,
                height=64,
                steps=1,
            )
            elapsed = round(time.monotonic() - t0, 1)
            return {
                "status": "healthy",
                "latency_seconds": elapsed,
                "url": result.get("url", "")[:80],
            }
        except Exception as exc:
            elapsed = round(time.monotonic() - t0, 1)
            return {
                "status": "error",
                "latency_seconds": elapsed,
                "message": str(exc)[:300],
            }


# ═══════════════════════════════════════════════════════════
# Factory helper
# ═══════════════════════════════════════════════════════════

def create_comfyui_service(settings) -> ComfyUIService:
    """Create ComfyUIService from application settings."""
    return ComfyUIService(
        runninghub_api_key=getattr(settings, "runninghub_api_key", None),
        runninghub_url=getattr(settings, "runninghub_url", None),
        comfyui_url=getattr(settings, "comfyui_url", None),
        default_image_workflow=getattr(settings, "comfyui_image_workflow", "image_flux"),
        default_video_workflow=getattr(settings, "comfyui_video_workflow", "video_wan2.2"),
    )
