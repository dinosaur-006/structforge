"""AIVideoPromptEngine — unified entry point for multi-platform prompt generation.

Usage:
    engine = AIVideoPromptEngine(platform="seedance")
    result = engine.generate(segment, product_name="旺仔牛奶", product_type="食品饮料")
    print(result.prompt_text)   # Ready-to-use Seedance prompt
    print(result.prompt_english) # Runway-compatible English prompt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembler import PromptAssembler, PromptResult
from .adapters.seedance import SeedanceAdapter
from .negative_prompts import select_negatives


@dataclass
class GeneratedPrompt:
    """Complete prompt output from the engine, ready for API call or user display."""

    segment_id: str
    segment_type: str
    platform: str

    # Primary prompt (platform-native format)
    prompt_text: str

    # Alternative platform prompts
    prompt_english: str      # Runway-compatible
    prompt_chinese: str      # Kling-compatible

    # Negative prompt
    negative_prompt: str

    # Production parameters
    camera: str
    visual_fx: str
    emotion: str
    pace: str = "正常"
    subtitle_anim: str = "淡入"
    duration: float = 5.0

    # API metadata
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    model: str = "doubao-seedance-2-0-260128"
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
    """Unified prompt generation engine supporting multiple platforms.

    Platform-adaptive: generates native-format prompts for Seedance, Runway, and Kling.
    Quality-gated: optional validation scores each prompt before returning.
    """

    def __init__(self, platform: str = "seedance") -> None:
        self.platform = platform
        self.assembler = PromptAssembler()
        self.seedance = SeedanceAdapter()

    def generate(
        self,
        segment: Any,
        *,
        product_name: str = "",
        product_type: str = "其他",
        validate: bool = False,
    ) -> GeneratedPrompt:
        """Generate a complete prompt from segment data.

        Args:
            segment: FinalSegment-compatible object
            product_name: Human-readable product name
            product_type: Broad product category
            validate: If True, run quality checks before returning

        Returns:
            GeneratedPrompt with platform-native + cross-platform prompts
        """
        # Assemble structured layers
        layers = self.assembler.assemble(
            segment=segment,
            product_name=product_name,
            product_type=product_type,
            platform=self.platform,
        )

        # Platform-specific formatting
        seg_type = str(getattr(segment, "type", "product"))
        visual = str(getattr(segment, "visual", "") or "")
        camera = str(getattr(segment, "camera", "静态") or "静态")
        visual_fx = str(getattr(segment, "visual_fx", "无") or "无")
        emotion = str(getattr(segment, "emotion", "亲切") or "亲切")
        pace = str(getattr(segment, "pace", "正常") or "正常")
        subtitle_anim = str(getattr(segment, "subtitle_anim", "淡入") or "淡入")
        duration = float(getattr(segment, "duration", 5.0))
        script = str(getattr(segment, "script", "") or "")
        seg_id = str(getattr(segment, "id", ""))

        # Primary prompt (Seedance format)
        prompt_text = self.seedance.build_prompt(
            segment_type=seg_type,
            product_name=product_name,
            product_type=product_type,
            visual_description=visual,
            script_text=script,
            camera=camera,
            visual_fx=visual_fx,
            emotion=emotion,
            duration=duration,
        )

        # English prompt (Runway-compatible)
        prompt_english = self._build_english_prompt(layers)

        # Chinese prompt (Kling-compatible)
        prompt_chinese = self._build_chinese_prompt(layers, emotion)

        # Negative prompt
        negative = select_negatives(
            self.platform,
            visual_fx=visual_fx,
            segment_type=seg_type,
            include_product=True,
        )

        # Cost estimation
        fps = 30
        frame_coeff = 0.8
        est_tokens = int(duration * fps * frame_coeff)
        est_cost = round(duration * fps * frame_coeff * 0.0003, 3)
        if est_cost < 0.01:
            est_cost = 0.01

        # API payload
        payload = {
            "model": "doubao-seedance-2-0-260128",
            "content": [{"type": "text", "text": prompt_text}],
            "duration": max(4, min(int(duration), 12)),
            "ratio": "9:16",
            "resolution": "720p",
            "watermark": False,
        }

        # Quality validation (if requested)
        quality_score = 0
        quality_passed = True
        if validate:
            quality_score, quality_passed = self._validate(prompt_text)

        return GeneratedPrompt(
            segment_id=seg_id,
            segment_type=seg_type,
            platform=self.platform,
            prompt_text=prompt_text,
            prompt_english=prompt_english,
            prompt_chinese=prompt_chinese,
            negative_prompt=negative,
            camera=camera,
            visual_fx=visual_fx,
            emotion=emotion,
            pace=pace,
            subtitle_anim=subtitle_anim,
            duration=duration,
            api_payload=payload,
            estimated_tokens=est_tokens,
            estimated_cost_usd=est_cost,
            subtitle_text=script,
            product_name=product_name,
            quality_score=quality_score,
            quality_passed=quality_passed,
            layers=layers,
        )

    def generate_batch(
        self,
        segments: list[Any],
        *,
        product_name: str = "",
        product_type: str = "其他",
    ) -> list[GeneratedPrompt]:
        """Generate prompts for all segments at once."""
        return [
            self.generate(s, product_name=product_name, product_type=product_type)
            for s in segments
        ]

    # ── Cross-platform prompt builders ──

    def _build_english_prompt(self, layers: PromptResult) -> str:
        """Build a Runway-compatible English prompt from structured layers."""
        camera_en = {
            "快推": "Fast dolly-in",
            "缓推": "Slow dolly-in",
            "拉远": "Slow dolly-out",
            "横移": "Slow pan right",
            "跟随": "Smooth gimbal tracking",
            "手持微晃": "Handheld phone camera",
            "静态": "Static locked-off tripod",
            "环绕": "Slow orbit around subject",
        }
        cam = camera_en.get(layers.camera_motion, "Slow dolly-in")

        return (
            f"{cam}: {layers.subject_text}. {layers.action_text}. "
            f"{layers.lighting}. Product commercial aesthetic, "
            f"minimal clean background, shallow depth of field. "
            f"{layers.duration:.0f}-second commercial shot."
        )

    def _build_chinese_prompt(self, layers: PromptResult, emotion: str) -> str:
        """Build a Kling-compatible Chinese prompt from structured layers."""
        atmosphere = {
            "紧迫": "充满紧迫感的", "惊讶": "令人惊叹的", "兴奋": "充满活力的",
            "亲切": "温馨治愈的", "权威": "专业严谨的", "感动": "令人感动的",
            "平静": "宁静舒适的",
        }.get(emotion, "")

        return (
            f"{atmosphere}产品广告画面。{layers.subject_text}，{layers.action_text}。"
            f"{layers.shot_size}，{layers.lighting}。整体色调协调悦目。"
        )

    def _validate(self, prompt_text: str) -> tuple[int, bool]:
        """Run quality checks via PromptQualityValidator. Returns (score, passed)."""
        from .validator import PromptQualityValidator
        validator = PromptQualityValidator()
        report = validator.validate(prompt_text, platform=self.platform)
        return report.score, report.passed
