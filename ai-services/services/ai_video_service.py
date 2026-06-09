"""AI video generation service — independent module decoupled from compositor.

Architecture:
    FinalSegment → AIVideoService.generate()
        ├── [API configured] → Seedance API → GeneratedVideo → compositor
        └── [API not configured] → PromptCard → prompt_card_renderer → compositor

This module is the single entry point for all AI video generation in StructForge.
Compositor no longer calls VideoGenerator directly — it calls this service.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import Settings
from services.prompt_engine.engine import AIVideoPromptEngine, GeneratedPrompt


# ══════════════════════════════════════════════════════════════════════════
# Data classes
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class PromptCard:
    """Returned when AI video API is not configured.

    Contains everything needed to:
    1. Render a prompt card into the video (via prompt_card_renderer)
    2. Display in the frontend PayloadPreviewDrawer
    3. Export as copyable text for external platforms
    """

    segment_id: str
    segment_type: str
    segment_label: str = ""

    # Multi-platform prompts
    prompt_text: str = ""           # Seedance-native prompt
    prompt_english: str = ""        # Runway-compatible
    prompt_chinese: str = ""        # Kling-compatible
    negative_prompt: str = ""

    # Production parameters
    camera: str = "静态"
    visual_fx: str = "无"
    emotion: str = "亲切"
    pace: str = "正常"
    subtitle_anim: str = "淡入"
    duration: float = 5.0

    # API metadata
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    api_endpoint: str = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    api_provider: str = "Volcano Ark / Seedance 2.0"
    model: str = "doubao-seedance-2-0-260128"
    api_payload: dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Context
    subtitle_text: str = ""
    product_name: str = ""
    platform_compatible: list[str] = field(default_factory=lambda: ["seedance", "runway", "kling"])

    @classmethod
    def from_generated_prompt(cls, gp: GeneratedPrompt, segment: Any) -> "PromptCard":
        """Create a PromptCard from a GeneratedPrompt + segment."""
        return cls(
            segment_id=gp.segment_id,
            segment_type=gp.segment_type,
            segment_label=str(getattr(segment, "label", "") or ""),
            prompt_text=gp.prompt_text,
            prompt_english=gp.prompt_english,
            prompt_chinese=gp.prompt_chinese,
            negative_prompt=gp.negative_prompt,
            camera=gp.camera,
            visual_fx=gp.visual_fx,
            emotion=gp.emotion,
            pace=gp.pace,
            subtitle_anim=gp.subtitle_anim,
            duration=gp.duration,
            api_payload=gp.api_payload,
            estimated_tokens=gp.estimated_tokens,
            estimated_cost_usd=gp.estimated_cost_usd,
            subtitle_text=gp.subtitle_text,
            product_name=gp.product_name,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for frontend PayloadPreviewDrawer."""
        return {
            "segment_id": self.segment_id,
            "segment_type": self.segment_type,
            "segment_label": self.segment_label,
            "duration": self.duration,
            "visual_prompt": self.prompt_text,
            "script_text": self.subtitle_text,
            "camera": self.camera,
            "visual_fx": self.visual_fx,
            "pace": self.pace,
            "emotion": self.emotion,
            "model": self.model,
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "api_provider": self.api_provider,
            "is_available": False,
            "api_payload": self.api_payload,
            "prompt_english": self.prompt_english,
            "prompt_chinese": self.prompt_chinese,
            "negative_prompt": self.negative_prompt,
            "platform_compatible": self.platform_compatible,
        }


@dataclass
class GeneratedVideo:
    """Returned when AI video API call succeeds."""

    segment_id: str
    video_path: Path
    duration: float
    platform: str = "seedance"
    generation_time: float = 0.0
    cost: float = 0.0


# ══════════════════════════════════════════════════════════════════════════
# AIVideoService
# ══════════════════════════════════════════════════════════════════════════

class AIVideoService:
    """Independent AI video generation service.

    Replaces inline VideoGenerator calls in compositor.py.
    Handles both real API calls and graceful PromptCard fallback.

    Usage:
        service = AIVideoService(settings)
        result = service.generate(segment, product_name="旺仔牛奶", product_type="食品饮料")
        if isinstance(result, GeneratedVideo):
            source_path = result.video_path  # real video
        elif isinstance(result, PromptCard):
            # render prompt card → FFmpeg → video
            card_png = render_prompt_card(result)
    """

    def __init__(
        self,
        settings: Settings,
        *,
        platform: str = "seedance",
    ) -> None:
        self.settings = settings
        self.platform = platform
        self.prompt_engine = AIVideoPromptEngine(platform=platform)
        self._api_available = bool(
            settings.doubao_image_api_key
            and settings.doubao_llm_endpoint
        )

    @property
    def api_available(self) -> bool:
        return self._api_available

    def generate(
        self,
        segment: Any,
        *,
        product_name: str = "",
        product_type: str = "其他",
    ) -> GeneratedVideo | PromptCard:
        """Generate AI video for a single segment.

        Returns GeneratedVideo if API is configured and call succeeds.
        Returns PromptCard if API is not configured (graceful fallback).
        """
        # Generate the prompt (needed for both paths)
        gen_prompt = self.prompt_engine.generate(
            segment,
            product_name=product_name,
            product_type=product_type,
        )

        # Try API call if available
        if self._api_available:
            video = self._call_seedance_api(gen_prompt, segment)
            if video is not None:
                return video
            # API call failed → fall through to PromptCard

        # Return prompt card for graceful degradation
        return PromptCard.from_generated_prompt(gen_prompt, segment)

    def generate_prompt_only(
        self,
        segment: Any,
        *,
        product_name: str = "",
        product_type: str = "其他",
    ) -> PromptCard:
        """Generate a PromptCard without attempting API call.

        Used when we KNOW the API is unavailable (avoids wasted attempts).
        """
        gen_prompt = self.prompt_engine.generate(
            segment,
            product_name=product_name,
            product_type=product_type,
        )
        return PromptCard.from_generated_prompt(gen_prompt, segment)

    def generate_batch_prompts(
        self,
        segments: list[Any],
        *,
        product_name: str = "",
        product_type: str = "其他",
    ) -> list[PromptCard]:
        """Generate PromptCards for multiple segments at once."""
        prompts = self.prompt_engine.generate_batch(
            segments,
            product_name=product_name,
            product_type=product_type,
        )
        return [PromptCard.from_generated_prompt(gp, seg) for gp, seg in zip(prompts, segments)]

    # ── Private: Seedance API call ──

    def _call_seedance_api(
        self,
        gen_prompt: GeneratedPrompt,
        segment: Any,
    ) -> GeneratedVideo | None:
        """Call Seedance 2.0 API. Returns None on failure."""
        import httpx

        output_dir = self.settings.output_dir / "aigc"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{gen_prompt.segment_id}_seedance.mp4"

        t0 = time.monotonic()
        try:
            # Submit task
            resp = httpx.post(
                "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
                headers={"Authorization": f"Bearer {self.settings.doubao_image_api_key}"},
                json={
                    "model": self.settings.doubao_video_model,
                    "content": [{"type": "text", "text": gen_prompt.prompt_text}],
                    "duration": max(4, min(int(gen_prompt.duration), 12)),
                    "ratio": gen_prompt.aspect_ratio,
                    "resolution": gen_prompt.resolution,
                    "watermark": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            task_id = resp.json().get("id", "")
            if not task_id:
                return None

            # Poll until complete (max 120s)
            for _ in range(40):
                time.sleep(3)
                qr = httpx.get(
                    f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.settings.doubao_image_api_key}"},
                    timeout=15,
                )
                qr.raise_for_status()
                payload = qr.json()
                status = payload.get("status", "")
                if status == "succeeded":
                    video_url = payload.get("content", {}).get("video_url", "") or payload.get("video_url", "")
                    if video_url:
                        vr = httpx.get(video_url, timeout=60)
                        vr.raise_for_status()
                        output_path.write_bytes(vr.content)
                        return GeneratedVideo(
                            segment_id=gen_prompt.segment_id,
                            video_path=output_path,
                            duration=gen_prompt.duration,
                            platform="seedance",
                            generation_time=time.monotonic() - t0,
                            cost=gen_prompt.estimated_cost_usd,
                        )
                    return None
                if status in ("failed", "expired"):
                    return None
            return None
        except Exception:
            return None
