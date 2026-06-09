"""Seedance 2.0 adapter — Chinese+English mixed prompts optimized for Doubao platform.

Seedance prompt formula (priority order):
    1. Format prefix (竖屏/横屏, aspect ratio)
    2. Product category context
    3. Subject description (前30词权重最高)
    4. Action description
    5. Camera language (Seedance-specific English terminology)
    6. Lighting & style
    7. Post-processing effects
    8. Technical flags (--ar, --style)
"""

from __future__ import annotations

from typing import Any

from ..vocabulary import (
    EMOTION_CAMERA_MAP,
    SEEDANCE_STYLE_PRESETS,
    resolve_product_vocab,
    resolve_segment_action,
    resolve_style_tone,
)
from ..negative_prompts import select_negatives


# Camera parameter → Seedance cinematography English terminology
_CAMERA_SEEDANCE: dict[str, str] = {
    "快推": "Dynamic fast 3D camera zoom-in, action-packed focus shot, rapid approach",
    "缓推": "Cinematic high-end slow push-in tracking shot, smooth elegant slide, gradual reveal",
    "拉远": "Slow dramatic pull-back reveal, wide establishing shot, expanding perspective",
    "横移": "Elegant dolly tracking shot, horizontal sweeping view, smooth lateral movement",
    "跟随": "Smooth follow-cam tracking, steady gimbal movement, fluid motion trailing subject",
    "手持微晃": "Intense realistic handheld camera shake, chaotic documentary aesthetic, raw authentic feel",
    "静态": "Locked-off stable tripod shot, hyper-focused framing, perfectly still composition",
    "环绕": "Slow orbital rotation around subject, 360-degree product showcase, cinematic arc shot",
}

# Visual FX → Seedance post-processing instructions
_FX_SEEDANCE: dict[str, str] = {
    "无": "Clean photorealistic render, no post effects, natural look",
    "震屏": "Screen shake visual effect, high energy impact, camera quake, intense vibration",
    "闪白": "Dramatic flash exposure lighting transition, high contrast bloom, brilliant white burst",
    "慢动作": "High-speed photography, crisp slow motion playback, 120fps smooth deceleration",
    "放大": "Dynamic scale-up zoom effect, cinematic crash zoom, dramatic magnification",
    "模糊过渡": "Cinematic lens blur transition, smooth defocus ramp, dreamy soft focus dissolve",
}

# Product type → Seedance category prefix
_CATEGORY_PREFIX: dict[str, str] = {
    "食品饮料": "食品饮料类",
    "美妆护肤": "美妆洗护类",
    "电子3C": "电子数码类",
    "服饰纺织": "服装配饰类",
    "家居厨具": "家居生活类",
    "日用百货": "生活好物类",
}


class SeedanceAdapter:
    """Generate Seedance 2.0 optimized prompts from segment data."""

    def __init__(self) -> None:
        pass

    def build_prompt(
        self,
        *,
        segment_type: str,
        product_name: str = "",
        product_type: str = "其他",
        visual_description: str = "",
        script_text: str = "",
        camera: str = "静态",
        visual_fx: str = "无",
        emotion: str = "亲切",
        duration: float = 5.0,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
    ) -> str:
        """Assemble a complete Seedance 2.0 prompt from segment data.

        Returns a prompt string ready for the Seedance API.
        """
        # Resolve vocabulary
        vocab = resolve_product_vocab(product_type, visual_description)
        emotion_cam = EMOTION_CAMERA_MAP.get(emotion, EMOTION_CAMERA_MAP["亲切"])

        # Layer 1: Category prefix
        category_cn = _CATEGORY_PREFIX.get(product_type, "好物推荐")
        ratio_label = "竖屏短视频画面" if aspect_ratio == "9:16" else "横屏短视频画面"

        # Layer 2: Subject + product
        product_identity = product_name or "产品"
        subject_textures = vocab.get("textures", ["clean", "professional"])
        texture_str = "、".join(subject_textures[:3])
        subject = self._build_subject(product_identity, visual_description, texture_str, product_type)

        # Layer 3: Action
        action = resolve_segment_action(segment_type, visual_description)

        # Layer 4: Camera
        camera_eng = _CAMERA_SEEDANCE.get(camera, _CAMERA_SEEDANCE["静态"])
        # Determine shot size
        shot_size = self._shot_size_for_type(segment_type)
        camera_line = f"{shot_size}，{camera_eng}"

        # Layer 5: Style / lighting
        lighting = vocab.get("lighting", "studio lighting, clean background")
        style_tone = resolve_style_tone(emotion, product_type)
        emotion_style = emotion_cam.get("style_tone", "")

        # Layer 6: Post-processing
        fx_eng = _FX_SEEDANCE.get(visual_fx, _FX_SEEDANCE["无"])

        # Layer 7: Constraints
        constraints = select_negatives(
            "seedance",
            visual_fx=visual_fx,
            segment_type=segment_type,
            include_product=True,
        )

        # Assemble full prompt
        prompt = (
            f"{ratio_label}，{aspect_ratio}构图：{category_cn}，电商带货风格。\n"
            f"{subject}\n"
            f"镜头语言：{camera_line}。\n"
            f"光影风格：{lighting}。{style_tone}。{emotion_style}\n"
            f"后期处理：{fx_eng}。\n"
            f"--ar {aspect_ratio} --style raw"
        )
        return prompt

    def build_negative(self, *, visual_fx: str = "无", segment_type: str = "product") -> str:
        """Return standalone negative prompt string."""
        return select_negatives(
            "seedance",
            visual_fx=visual_fx,
            segment_type=segment_type,
            include_product=True,
        )

    # ── Private helpers ──

    def _build_subject(self, product_name: str, visual: str, texture: str, product_type: str) -> str:
        """Build the subject description (Layer 1 of the prompt).

        Combines product name + visual description + texture keywords
        into a natural Chinese sentence optimized for Seedance.
        """
        # Business/product style prefix
        biz_prefix = "电商产品特写："

        # Clean visual description
        import re
        clean_visual = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual)
        clean_visual = re.sub(r'【[镜字速情视]】', '', clean_visual)
        clean_visual = re.sub(r'\s+', ' ', clean_visual).strip()

        if not clean_visual or clean_visual in ("画面", "画面描述", "无"):
            clean_visual = f"{product_name}的产品特写展示"

        # Product-type-specific framing
        framing = {
            "食品饮料": f"{product_name}，{texture}质感，诱人的美食广告画面",
            "美妆护肤": f"{product_name}，{texture}质地，精致的美妆产品展示",
            "电子3C": f"{product_name}，{texture}外观，科技感十足的产品特写",
            "服饰纺织": f"{product_name}，{texture}面料，时尚的服装展示",
            "家居厨具": f"{product_name}，{texture}材质，温馨的家居场景",
        }

        subject_line = framing.get(product_type, f"{biz_prefix}{product_name}，{texture}材质，{clean_visual}")
        return subject_line

    def _shot_size_for_type(self, segment_type: str) -> str:
        """Determine optimal shot size for segment type."""
        shot_map = {
            "hook": "特写镜头",
            "pain": "中近景",
            "product": "微距特写",
            "proof": "中近景",
            "cta": "特写镜头",
            "demo": "中近景",
            "offer": "特写镜头",
            "compare": "中景",
        }
        return shot_map.get(segment_type, "特写镜头")
