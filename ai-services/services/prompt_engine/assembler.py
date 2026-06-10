"""PromptAssembler — orchestrates the five-layer prompt structure.

Takes segment data + product metadata + platform target → produces a
structured PromptResult that each adapter can format natively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .vocabulary import (
    EMOTION_CAMERA_MAP,
    resolve_product_vocab,
    resolve_segment_action,
)
from .negative_prompts import select_negatives


@dataclass
class PromptResult:
    """Structured prompt output before platform-specific formatting."""

    segment_id: str
    segment_type: str
    platform: str

    # Layer 1: Subject
    subject_text: str
    # Layer 2: Action
    action_text: str
    # Layer 3: Camera
    camera_motion: str           # e.g. "快推"
    shot_size: str               # e.g. "特写镜头"
    camera_platform_vocab: str   # e.g. "Cinematic slow push-in tracking shot"
    # Layer 4: Style
    lighting: str                # e.g. "Soft key light from 45° left"
    emotion_tone: str            # e.g. "warm and inviting"
    # Layer 5: Constraints
    negative_prompt: str         # assembled negative prompt string

    # Fields with defaults
    subject_textures: list[str] = field(default_factory=list)
    clean_visual: str = ""         # Cleaned LLM visual description
    segment_script: str = ""       # The segment's spoken script
    duration: float = 5.0
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    product_name: str = ""
    product_type: str = "其他"
    visual_fx: str = "无"
    subtitle_text: str = ""

    @property
    def all_textures(self) -> str:
        return "、".join(self.subject_textures[:3]) if self.subject_textures else ""


class PromptAssembler:
    """Orchestrate the five-layer prompt assembly from segment + product data."""

    def assemble(
        self,
        *,
        segment: Any,
        product_name: str = "",
        product_type: str = "其他",
        platform: str = "seedance",
        product_visual: dict | None = None,
    ) -> PromptResult:
        """Build a complete PromptResult from segment and product metadata.

        Args:
            segment: FinalSegment or compatible object with fields:
                id, type, visual, camera, visual_fx, emotion, duration, script
            product_name: Human-readable product name (e.g. "旺仔牛奶")
            product_type: Broad product category (e.g. "食品饮料")
            platform: Target platform ("seedance" | "runway" | "kling")
        """
        seg_type = str(getattr(segment, "type", "product"))
        visual = str(getattr(segment, "visual", "") or "")
        camera = str(getattr(segment, "camera", "静态") or "静态")
        visual_fx = str(getattr(segment, "visual_fx", "无") or "无")
        emotion = str(getattr(segment, "emotion", "亲切") or "亲切")
        duration = float(getattr(segment, "duration", 5.0))
        script = str(getattr(segment, "script", "") or "")
        seg_id = str(getattr(segment, "id", ""))

        # Clean visual description
        import re
        clean_visual = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual)
        clean_visual = re.sub(r'【[镜字速情视]】', '', clean_visual)
        clean_visual = re.sub(r'\s+', ' ', clean_visual).strip()

        # ── Layer 1: Subject ──
        # Always use English vocabulary. Product image Vision analysis enriches
        # matching but never injects Chinese text into the English prompt.
        vocab = resolve_product_vocab(product_type, clean_visual)
        subject_textures = list(vocab.get("textures", ["clean", "professional"]))
        # Enrich lighting with vision colors if available
        vision_colors = product_visual.get("colors", []) if product_visual else []
        if vision_colors:
            vocab["lighting"] = f"product photography, dominant colors: {', '.join(vision_colors[:3])}"
        subject_text = self._build_subject_text(product_name, clean_visual, subject_textures, product_type)

        # ── Layer 2: Action ──
        action_text = resolve_segment_action(seg_type, clean_visual)

        # ── Layer 3: Camera ──
        emotion_cam = EMOTION_CAMERA_MAP.get(emotion, EMOTION_CAMERA_MAP["亲切"])
        camera_motion = camera if camera else emotion_cam["camera"]
        shot_size = self._shot_size_for_type(seg_type)
        camera_vocab = self._camera_vocab_for_platform(camera_motion, platform)

        # ── Layer 4: Style ──
        lighting = vocab.get("lighting", "studio lighting, clean background")
        emotion_tone = emotion_cam.get("style_tone", "")

        # ── Layer 5: Constraints ──
        negative = select_negatives(
            platform,
            visual_fx=visual_fx,
            segment_type=seg_type,
            include_product=True,
        )

        return PromptResult(
            segment_id=seg_id,
            segment_type=seg_type,
            platform=platform,
            subject_text=subject_text,
            subject_textures=subject_textures,
            clean_visual=clean_visual,
            segment_script=script,
            action_text=action_text,
            camera_motion=camera_motion,
            shot_size=shot_size,
            camera_platform_vocab=camera_vocab,
            lighting=lighting,
            emotion_tone=emotion_tone,
            negative_prompt=negative,
            duration=duration,
            product_name=product_name,
            product_type=product_type,
            visual_fx=visual_fx,
            subtitle_text=script,
        )

    # ── Private helpers ──

    def _build_subject_text(self, product_name: str, visual: str, textures: list[str], product_type: str) -> str:
        """Build Layer 1 subject text in Chinese."""
        name = product_name or "产品"
        tex = "、".join(textures[:3]) if textures else "精致"

        framing: dict[str, str] = {
            "食品饮料": f"{name}，{tex}质感，诱人的美食广告画面",
            "美妆护肤": f"{name}，{tex}质地，精致的美妆产品展示",
            "电子3C": f"{name}，{tex}外观，科技感十足的产品特写",
            "服饰纺织": f"{name}，{tex}面料，时尚的服装展示",
            "家居厨具": f"{name}，{tex}材质，温馨的家居场景",
        }
        base = framing.get(product_type, f"电商产品特写：{name}，{tex}材质，{visual}")
        return base

    def _shot_size_for_type(self, segment_type: str) -> str:
        return {
            "hook": "特写镜头", "pain": "中近景", "product": "微距特写",
            "proof": "中近景", "cta": "特写镜头", "demo": "中近景",
            "offer": "特写镜头", "compare": "中景",
        }.get(segment_type, "特写镜头")

    def _camera_vocab_for_type(self, camera: str) -> str:
        """Legacy fallback (Seedance-specific). Use _camera_vocab_for_platform for new code."""
        return self._camera_vocab_for_platform(camera, "seedance")

    def _camera_vocab_for_platform(self, camera: str, platform: str) -> str:
        vocab: dict[str, dict[str, str]] = {
            "seedance": {
                "快推": "Dynamic fast 3D camera zoom-in, action-packed focus shot",
                "缓推": "Cinematic high-end slow push-in tracking shot, smooth elegant slide",
                "拉远": "Slow dramatic pull-back reveal, wide establishing shot",
                "横移": "Elegant dolly tracking shot, horizontal sweeping view",
                "跟随": "Smooth follow-cam tracking, steady gimbal movement",
                "手持微晃": "Intense realistic handheld camera shake, documentary aesthetic",
                "静态": "Locked-off stable tripod shot, hyper-focused framing",
                "环绕": "Slow orbital rotation around subject, 360-degree product showcase",
            },
            "runway": {
                "快推": "Fast dolly-in, rapid push toward subject",
                "缓推": "Slow dolly-in, gentle push toward subject",
                "拉远": "Slow dolly-out, reveal context",
                "横移": "Slow pan right, controlled horizontal reveal",
                "跟随": "Smooth gimbal tracking, floating camera",
                "手持微晃": "Handheld phone camera, slight natural sway",
                "静态": "Static locked-off tripod, fixed frame",
                "环绕": "Slow 180-degree orbit around product",
            },
            "kling": {
                "快推": "镜头快速推近，画面聚焦到产品",
                "缓推": "镜头缓缓推近，画面逐渐聚焦",
                "拉远": "镜头慢慢拉远，视野逐渐开阔",
                "横移": "镜头水平横移，展示产品侧面",
                "跟随": "镜头平滑跟随主体移动",
                "手持微晃": "手持镜头轻微晃动，真实临场感",
                "静态": "固定机位，画面稳定不动",
                "环绕": "镜头环绕主体旋转，360度展示",
            },
        }
        platform_vocab = vocab.get(platform, vocab["seedance"])
        return platform_vocab.get(camera, platform_vocab["静态"])
