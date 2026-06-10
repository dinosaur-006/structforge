"""FluxPromptGenerator — LLM-powered prompt creation for RunningHub ComfyUI Flux."""

from __future__ import annotations

import logging
from typing import Any

from config import Settings

log = logging.getLogger(__name__)

FLUX_SYSTEM_PROMPT = """You are a world-class AI commercial photographer and prompt engineer.
Create a detailed, professional-grade Flux prompt for a single product advertisement frame.

## CRITICAL RULES
- Output ONLY the raw prompt text. No quotes, no markdown, no explanations.
- Pure English. NO Chinese characters anywhere.
- 150-250 words. Be thorough and specific.
- The image MUST match the given resolution and aspect ratio.

## PROMPT STRUCTURE
1. COMPOSITION: Specify the exact shot type, camera angle, and framing
2. SUBJECT: Describe the SPECIFIC product in extreme detail (colors, materials, textures, brand name)
3. LIGHTING: Name specific lighting setups (key light, rim light, fill light, their directions and qualities)
4. ENVIRONMENT: Describe the background and setting in detail
5. ACTION/DYNAMICS: What is happening in the frame
6. TECHNICAL: Camera specs, lens type, depth of field, resolution

## QUALITY REQUIREMENTS
- Use professional commercial photography vocabulary
- Include material properties: matte, glossy, metallic, textured, translucent, crystalline
- Include lighting terms: soft diffused key light, hard rim light, golden hour, studio strobe, butterfly lighting, Rembrandt lighting
- Include camera terms: macro lens, 85mm prime, tilt-shift, bokeh, deep focus, anamorphic
- Include post-processing: color graded, retouched, high dynamic range, sharp detail
- Always end with: "commercial photography, hyperrealistic, 8k resolution, masterpiece"
"""


class FluxPromptGenerator:
    """Generate Flux-optimized English prompts using Doubao LLM.

    Falls back to rule-based PromptEngine if LLM is unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm_available = bool(settings.doubao_llm_endpoint and settings.doubao_llm_api_key)

    def generate(
        self,
        *,
        segment_type: str,
        script: str,
        visual: str,
        camera: str = "静态",
        emotion: str = "亲切",
        duration: float = 3.0,
        product_name: str = "",
        product_type: str = "其他",
        product_vision_tags: list[str] | None = None,
        product_vision_colors: list[str] | None = None,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Generate a Flux-optimized English prompt via LLM, with rule-based fallback.

        Returns the English prompt string (never empty).
        """
        # Try LLM first
        if self._llm_available:
            try:
                prompt = self._call_llm(
                    segment_type=segment_type, script=script, visual=visual,
                    camera=camera, emotion=emotion, duration=duration,
                    product_name=product_name, product_type=product_type,
                    vision_tags=product_vision_tags, vision_colors=product_vision_colors,
                    width=width, height=height,
                )
                if prompt and len(prompt) > 30:
                    # Strip any Chinese characters as safety net
                    import re
                    prompt = re.sub(r'[一-鿿　-〿＀-￯]+', '', prompt)
                    prompt = re.sub(r'\s+', ' ', prompt).strip()
                    if len(prompt) > 50:
                        return prompt
                    log.warning("LLM prompt too short after cleaning, falling back to rule-based")
            except Exception as exc:
                log.warning("LLM prompt generation failed: %s, falling back to rule-based", exc)

        # Fallback: rule-based PromptEngine
        return self._rule_based_fallback(
            segment_type=segment_type, script=script, visual=visual,
            camera=camera, emotion=emotion, duration=duration,
            product_name=product_name, product_type=product_type,
        )

    def _call_llm(
        self,
        segment_type: str, script: str, visual: str,
        camera: str, emotion: str, duration: float,
        product_name: str, product_type: str,
        vision_tags: list[str] | None, vision_colors: list[str] | None,
        width: int = 1080, height: int = 1920,
    ) -> str:
        """Call Doubao LLM to generate a Flux prompt."""
        from services.llm_client import RobustLLMClient

        vision_hint = ""
        if vision_tags:
            vision_hint = f"Product image analysis detected: {', '.join(vision_tags[:8])}"
            if vision_colors:
                vision_hint += f". Dominant colors: {', '.join(vision_colors[:3])}."

        aspect = "vertical 9:16" if height > width else "horizontal 16:9" if width > height else "square 1:1"

        segment_type_cn = {"hook":"opening hook","pain":"pain point","product":"hero product showcase","proof":"proof demonstration","cta":"call to action"}.get(segment_type, segment_type)
        camera_cn = {"快推":"fast push-in dolly zoom","缓推":"slow cinematic push-in","拉远":"pull-back reveal","横移":"dolly tracking lateral","跟随":"smooth follow-cam gimbal","手持微晃":"handheld documentary shake","静态":"locked-off tripod static","环绕":"360 orbital rotation"}.get(camera, camera)
        emotion_cn = {"惊讶":"surprising shocking dramatic","紧迫":"urgent intense high-energy","亲切":"warm inviting cozy","权威":"authoritative professional clinical","感动":"emotional heartwarming nostalgic","兴奋":"excited energetic vibrant","平静":"calm serene peaceful"}.get(emotion, emotion)

        llm_prompt = f"""{FLUX_SYSTEM_PROMPT}

## PRODUCT TO PHOTOGRAPH
Brand: {product_name}
Category: {product_type}
{vision_hint}

## STYLE CONSISTENCY — CRITICAL
This is ONE shot in a multi-shot commercial sequence. ALL shots in this sequence MUST share:
- Same lighting style: warm commercial studio, consistent key-to-fill ratio
- Same color palette: based on the product's actual colors from the vision analysis
- Same background treatment: consistent background across all shots
- Same camera language: smooth professional movement, consistent lens character
- Same post-processing: matching color grade across all shots

## PRODUCT NAME — ABSOLUTE REQUIREMENT
The product is "{product_name}". You MUST use the ROMANIZED/ENGLISH transliteration of this name in the prompt.
NEVER use Chinese characters. Use the Pinyin or English brand name.
NEVER substitute with generic terms like "cookie", "beverage", "drink", "snack" or "product".
Example: if the product is "元气森林", use "Yuanqi Forest" not the Chinese characters.

## SHOT SPECIFICATIONS
Segment: {segment_type_cn}
Camera movement: {camera_cn}
Mood: {emotion_cn}
Resolution: {width}x{height} ({aspect})

## CREATIVE DIRECTION
Scene: {visual}
This scene appears alongside the voiceover: "{script}"

## TASK
Create a complete, detailed Flux prompt following the STRUCTURE above. Include ALL 6 sections (composition, subject, lighting, environment, action, technical).
The prompt MUST be specific to {product_name}. Use the actual product name, never replace it with generic terms.
Make the prompt 150-250 words. Output ONLY the raw prompt:"""

        client = RobustLLMClient(
            str(self.settings.doubao_llm_endpoint or ""),
            str(self.settings.doubao_llm_api_key or ""),
            str(self.settings.doubao_llm_model),
            timeout=30,
        )
        result = client.complete_text(llm_prompt, max_tokens=800)
        return result.strip().strip('"').strip("'")

    def _rule_based_fallback(
        self,
        segment_type: str, script: str, visual: str,
        camera: str, emotion: str, duration: float,
        product_name: str, product_type: str,
    ) -> str:
        """Use the existing PromptEngine as fallback."""
        from services.prompt_engine.engine import AIVideoPromptEngine

        class _Seg:
            def __init__(self):
                self.id = "fallback"
                self.type = segment_type
                self.visual = visual
                self.camera = camera
                self.emotion = emotion
                self.script = script
                self.duration = duration
                self.visual_fx = "无"
                self.label = segment_type

        engine = AIVideoPromptEngine(platform="flux")
        result = engine.generate(
            _Seg(),
            product_name=product_name,
            product_type=product_type,
        )
        return result.prompt_english
