"""AIVideoPromptEngine — Flux-optimized English prompt generation for RunningHub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembler import PromptAssembler, PromptResult
from .negative_prompts import select_negatives


@dataclass
class GeneratedPrompt:
    """Complete prompt output for RunningHub ComfyUI Flux + WAN 2.2."""

    segment_id: str
    segment_type: str
    platform: str = "flux"

    # Primary prompt (Flux-optimized English)
    prompt_english: str = ""

    # Negative prompt
    negative_prompt: str = ""

    # Production parameters
    camera: str = ""
    visual_fx: str = ""
    emotion: str = ""
    pace: str = "正常"
    subtitle_anim: str = "淡入"
    duration: float = 5.0

    # API metadata
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    model: str = "flux"
    api_payload: dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Subtitle / context
    subtitle_text: str = ""
    product_name: str = ""

    # Quality metadata
    quality_score: int = 0
    quality_passed: bool = True

    # Structured layers (for debugging / display)
    layers: PromptResult | None = None


class AIVideoPromptEngine:
    """Flux-optimized English prompt generator for RunningHub ComfyUI.

    Generates prompts for both Flux (text-to-image) and WAN 2.2 (image-to-video).
    """

    def __init__(self, platform: str = "flux") -> None:
        self.platform = platform
        self.assembler = PromptAssembler()

    def generate(
        self,
        segment: Any,
        *,
        product_name: str = "",
        product_type: str = "其他",
        product_visual: dict | None = None,
    ) -> GeneratedPrompt:
        """Generate a complete Flux prompt from segment data."""
        layers = self.assembler.assemble(
            segment=segment,
            product_name=product_name,
            product_type=product_type,
            platform=self.platform,
            product_visual=product_visual,
        )

        seg_type = str(getattr(segment, "type", "product"))
        camera = str(getattr(segment, "camera", "静态") or "静态")
        visual_fx = str(getattr(segment, "visual_fx", "无") or "无")
        emotion = str(getattr(segment, "emotion", "亲切") or "亲切")
        pace = str(getattr(segment, "pace", "正常") or "正常")
        subtitle_anim = str(getattr(segment, "subtitle_anim", "淡入") or "淡入")
        duration = float(getattr(segment, "duration", 5.0))
        script = str(getattr(segment, "script", "") or "")
        seg_id = str(getattr(segment, "id", ""))

        # Flux English prompt
        prompt_english = self._build_english_prompt(layers)

        # Negative prompt
        negative = select_negatives(
            self.platform,
            visual_fx=visual_fx,
            segment_type=seg_type,
            include_product=True,
        )

        return GeneratedPrompt(
            segment_id=seg_id,
            segment_type=seg_type,
            platform=self.platform,
            prompt_english=prompt_english,
            negative_prompt=negative,
            camera=camera,
            visual_fx=visual_fx,
            emotion=emotion,
            pace=pace,
            subtitle_anim=subtitle_anim,
            duration=duration,
            subtitle_text=script,
            product_name=product_name,
            layers=layers,
        )

    def generate_batch(
        self,
        segments: list[Any],
        *,
        product_name: str = "",
        product_type: str = "其他",
        product_visual: dict | None = None,
    ) -> list[GeneratedPrompt]:
        """Generate Flux prompts for multiple segments at once."""
        return [
            self.generate(seg, product_name=product_name, product_type=product_type, product_visual=product_visual)
            for seg in segments
        ]

    # ── Prompt builder ──

    def _build_english_prompt(self, layers: PromptResult) -> str:
        """Build a Flux-optimized English prompt from ALL structured layers."""
        camera_en = {
            "快推": "fast dolly-in, dynamic zoom, high energy approach",
            "缓推": "slow cinematic push-in, smooth elegant tracking, gradual reveal",
            "拉远": "slow pull-back reveal, wide establishing shot, expanding view",
            "横移": "dolly tracking shot, horizontal sweeping, lateral movement",
            "跟随": "smooth follow-cam, steady gimbal, fluid tracking motion",
            "手持微晃": "handheld camera shake, documentary raw style, authentic feel",
            "静态": "static locked-off tripod, stable composition, hyper-focused",
            "环绕": "slow orbit around subject, 360 degree product showcase, cinematic arc",
        }
        cam = camera_en.get(layers.camera_motion, "slow cinematic push-in")

        tex = layers.subject_textures
        texture_desc = ", ".join(tex[:3]) if tex else "clean, professional"
        subjects_en = _resolve_english_subject(layers.product_type, layers.clean_visual)
        action_en = _resolve_english_action(layers.segment_type, layers.clean_visual)

        SEGMENT_FRAMING: dict[str, str] = {
            "hook": f"dramatic attention-grabbing opening, {subjects_en}, bold eye-catching shot, {texture_desc} texture, {action_en}",
            "pain": f"relatable problem scene, {subjects_en}, before the solution, {texture_desc} look, {action_en}",
            "product": f"premium hero product shot, {subjects_en}, exquisite detail, {texture_desc} surface, {action_en}",
            "proof": f"scientific comparison demonstration, {subjects_en}, side by side, verified evidence, {action_en}",
            "cta": f"compelling call to action, {subjects_en}, limited offer, urgent purchase moment, {action_en}",
        }
        scene = SEGMENT_FRAMING.get(layers.segment_type, f"professional product shot, {subjects_en}, {action_en}")

        CATEGORY_KW: dict[str, str] = {
            "食品饮料": "food photography, delicious gourmet, appetizing culinary presentation",
            "美妆护肤": "beauty product photography, luxury skincare, elegant cosmetic radiant",
            "电子3C": "tech product photography, sleek modern gadget, premium electronics",
            "服饰纺织": "fashion photography, elegant fabric, editorial clothing showcase",
            "家居厨具": "home product photography, cozy kitchen interior, warm lifestyle",
        }
        cat = CATEGORY_KW.get(layers.product_type, "product photography, commercial advertising, e-commerce")

        return (
            f"vertical 9:16 composition, {cat}. "
            f"{scene}. "
            f"{cam}. "
            f"{layers.lighting}. "
            f"commercial photography, photorealistic, 8k resolution, "
            f"shallow depth of field, professional color grading"
        )

# ── Module-level helpers ──

def _resolve_english_subject(product_type: str, visual_hint: str) -> str:
    from .vocabulary import resolve_product_vocab
    vocab = resolve_product_vocab(product_type, visual_hint)
    subjects = vocab.get("subjects", ["product", "item"])
    return ", ".join(subjects[:2]) if subjects else "product showcase"


def _resolve_english_action(segment_type: str, visual_hint: str) -> str:
    from .vocabulary import SEGMENT_ACTION_HINTS
    hints = SEGMENT_ACTION_HINTS.get(segment_type, SEGMENT_ACTION_HINTS.get("product", ["being showcased"]))
    if visual_hint:
        hint_words = set(visual_hint.lower())
        for hint in hints:
            words = set(hint.lower().split())
            if len(hint_words & words) >= 1:
                return hint
    return hints[0]
