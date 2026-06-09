"""Runway Gen-3/Gen-4 adapter — pure English cinematic prompts.

Runway prompt formula (15-30 words optimal):
    {Camera move}: {Subject description}. {Action}. {Lighting/Environment}. {Mood/Lens}.

Key differences from Seedance:
    - Pure English (no Chinese)
    - Shorter is better (under 30 words ideal)
    - Film/cinematography terminology preferred
    - Reference images strongly recommended for product consistency
"""

from __future__ import annotations

from ..vocabulary import EMOTION_CAMERA_MAP, resolve_product_vocab, resolve_segment_action
from ..negative_prompts import select_negatives


_CAMERA_RUNWAY: dict[str, str] = {
    "快推": "Fast dolly-in, rapid push toward subject",
    "缓推": "Slow dolly-in, gentle push toward subject",
    "拉远": "Slow dolly-out, reveal full context",
    "横移": "Slow pan right, controlled horizontal reveal",
    "跟随": "Smooth gimbal tracking, floating camera movement",
    "手持微晃": "Handheld phone camera, slight natural sway",
    "静态": "Static locked-off tripod, fixed frame composition",
    "环绕": "Slow 180-degree orbit around product, turntable feel",
}

_SHOT_RUNWAY: dict[str, str] = {
    "hook": "Extreme close-up",
    "pain": "Medium shot",
    "product": "Macro close-up",
    "proof": "Medium close-up",
    "cta": "Close-up",
    "demo": "Medium shot",
    "offer": "Close-up",
    "compare": "Wide shot",
}

_LENS_RUNWAY: dict[str, str] = {
    "hook": "24mm wide lens, dramatic perspective",
    "pain": "35mm normal lens, natural feel",
    "product": "50mm macro lens, shallow depth of field",
    "proof": "50mm normal lens, clean detail",
    "cta": "35mm lens, intimate framing",
}


class RunwayAdapter:
    """Generate Runway Gen-3/Gen-4 optimized prompts."""

    def build_prompt(
        self,
        *,
        segment_type: str = "product",
        product_name: str = "",
        product_type: str = "other",
        visual_description: str = "",
        camera: str = "静态",
        visual_fx: str = "无",
        emotion: str = "亲切",
        duration: float = 5.0,
    ) -> str:
        """Build a Runway-optimized English prompt."""
        import re

        # Clean visual
        clean_visual = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual_description)
        clean_visual = re.sub(r'【[镜字速情视]】', '', clean_visual)
        clean_visual = re.sub(r'\s+', ' ', clean_visual).strip()

        # Vocabulary
        vocab = resolve_product_vocab(product_type, clean_visual)
        emotion_cam = EMOTION_CAMERA_MAP.get(emotion, EMOTION_CAMERA_MAP["亲切"])

        # Camera
        camera_en = _CAMERA_RUNWAY.get(camera, _CAMERA_RUNWAY["静态"])
        shot = _SHOT_RUNWAY.get(segment_type, "Close-up")
        lens = _LENS_RUNWAY.get(segment_type, "50mm macro lens")

        # Subject
        product = product_name or "product"
        textures = vocab.get("textures", ["clean", "premium"])
        tex = ", ".join(textures[:2])
        subject = f"{shot} of {product}, {tex} texture, {clean_visual}" if clean_visual else f"{shot} of {product}, {tex} finish"

        # Action
        action = resolve_segment_action(segment_type, clean_visual)

        # Lighting
        lighting = vocab.get("lighting", "soft studio lighting, clean background")

        # Style from emotion
        style_map = {
            "亲切": "warm and inviting, natural skin tones",
            "紧迫": "high contrast, urgent energy, dramatic spotlight",
            "兴奋": "vibrant colors, dynamic energy, celebratory mood",
            "权威": "professional confidence, clean lighting, premium feel",
            "感动": "emotional warmth, golden hour glow, nostalgic atmosphere",
            "平静": "calm and serene, soft diffused light, gentle mood",
            "惊讶": "dramatic contrast, shock value, bright highlight",
        }
        style = style_map.get(emotion, "professional commercial aesthetic")

        # FX adaptation
        fx_map = {"震屏": "subtle handheld shake", "闪白": "bright flash transition",
                   "慢动作": "slow motion capture", "放大": "crash zoom effect",
                   "模糊过渡": "lens blur transition"}
        fx = fx_map.get(visual_fx, "")

        # Assemble
        prompt = (
            f"{camera_en}: {subject}. {action}. "
            f"{lighting}. {style}, {lens}. "
            f"{duration:.0f}-second commercial shot."
        )
        if fx:
            prompt += f" {fx}."

        return prompt

    def build_negative(self, *, visual_fx: str = "无", segment_type: str = "product") -> str:
        return select_negatives("runway", visual_fx=visual_fx, segment_type=segment_type, include_product=True)
