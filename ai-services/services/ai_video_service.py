"""AI visual generation service — Flux prompt generation for RunningHub ComfyUI.

Architecture:
    FinalSegment → AIVideoService.generate_prompt_only() → Flux prompt
    → render_pipeline → ComfyUI Flux (image) + optional WAN 2.2 (video)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import Settings
from services.prompt_engine.engine import AIVideoPromptEngine, GeneratedPrompt


@dataclass
class PromptCard:
    """Flux prompt card — produced for each segment, consumed by render pipeline."""

    segment_id: str
    segment_type: str
    segment_label: str = ""

    # Flux prompt
    prompt_english: str = ""
    negative_prompt: str = ""

    # Production parameters
    camera: str = "静态"
    visual_fx: str = "无"
    emotion: str = "亲切"
    pace: str = "正常"
    subtitle_anim: str = "淡入"
    duration: float = 5.0

    # Context
    subtitle_text: str = ""
    product_name: str = ""

    @classmethod
    def from_generated_prompt(cls, gp: GeneratedPrompt, segment: Any) -> "PromptCard":
        return cls(
            segment_id=gp.segment_id,
            segment_type=gp.segment_type,
            segment_label=str(getattr(segment, "label", "") or ""),
            prompt_english=gp.prompt_english,
            negative_prompt=gp.negative_prompt,
            camera=gp.camera,
            visual_fx=gp.visual_fx,
            emotion=gp.emotion,
            pace=gp.pace,
            subtitle_anim=gp.subtitle_anim,
            duration=gp.duration,
            subtitle_text=gp.subtitle_text,
            product_name=gp.product_name,
        )


class AIVideoService:
    """Single entry point for AI visual prompt generation in StructForge.

    Only generates Flux prompts — no API calls. The render pipeline calls
    ComfyUI directly for image/video generation.
    """

    def __init__(self, settings: Settings, platform: str = "flux") -> None:
        self.settings = settings
        self.prompt_engine = AIVideoPromptEngine(platform=platform)

    def generate_prompt_only(
        self,
        segment: Any,
        *,
        product_name: str = "",
        product_type: str = "其他",
        product_visual: dict | None = None,
    ) -> PromptCard:
        """Generate a Flux PromptCard without calling any external API."""
        gen_prompt = self.prompt_engine.generate(
            segment,
            product_name=product_name,
            product_type=product_type,
            product_visual=product_visual,
        )
        return PromptCard.from_generated_prompt(gen_prompt, segment)

    def generate_batch_prompts(
        self,
        segments: list[Any],
        *,
        product_name: str = "",
        product_type: str = "其他",
        product_visual: dict | None = None,
    ) -> list[PromptCard]:
        """Generate Flux PromptCards for multiple segments at once."""
        prompts = self.prompt_engine.generate_batch(
            segments,
            product_name=product_name,
            product_type=product_type,
            product_visual=product_visual,
        )
        return [PromptCard.from_generated_prompt(gp, seg) for gp, seg in zip(prompts, segments)]
