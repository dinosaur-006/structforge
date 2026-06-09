"""Kling adapter — Chinese emotional-driven prompts for Kuaishou Kling.

Kling prompt formula:
    {氛围前缀}。{主体描述}，{动作描述}。{镜头描述}，{光影氛围}。{风格基调}。

Key differences from Seedance:
    - Pure Chinese (no English)
    - Emotion-driven atmosphere
    - Character/scene consistency is a strength
    - Warm, cinematic tone preferred
"""

from __future__ import annotations

from ..vocabulary import EMOTION_CAMERA_MAP, resolve_product_vocab, resolve_segment_action
from ..negative_prompts import select_negatives


_CAMERA_KLING: dict[str, str] = {
    "快推": "镜头快速推近，画面聚焦到产品上，充满冲击力",
    "缓推": "镜头缓缓推近，画面逐渐聚焦到产品，平滑流畅",
    "拉远": "镜头慢慢拉远，视野逐渐开阔，揭示全景",
    "横移": "镜头水平横移，展示产品侧面细节",
    "跟随": "镜头平滑跟随主体移动，流畅自然",
    "手持微晃": "手持镜头轻微晃动，真实的临场感",
    "静态": "固定机位，画面稳定不动，构图精致",
    "环绕": "镜头环绕主体缓缓旋转，360度全方位展示",
}

_ATMOSPHERE_KLING: dict[str, str] = {
    "紧迫": "充满紧张感和紧迫感的",
    "惊讶": "令人惊叹的",
    "兴奋": "充满活力的",
    "亲切": "温馨治愈的",
    "权威": "专业严谨的",
    "感动": "令人感动的",
    "平静": "宁静舒适的",
}


class KlingAdapter:
    """Generate Kling-optimized Chinese prompts."""

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
        """Build a Kling-optimized Chinese prompt."""
        import re

        # Clean visual
        clean_visual = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual_description)
        clean_visual = re.sub(r'【[镜字速情视]】', '', clean_visual)
        clean_visual = re.sub(r'\s+', ' ', clean_visual).strip()

        # Vocabulary
        vocab = resolve_product_vocab(product_type, clean_visual)
        emotion_cam = EMOTION_CAMERA_MAP.get(emotion, EMOTION_CAMERA_MAP["亲切"])

        # Atmosphere prefix
        atmosphere = _ATMOSPHERE_KLING.get(emotion, "")
        type_label = {
            "食品饮料": "食品广告画面", "美妆护肤": "美妆产品展示",
            "电子3C": "数码产品特写", "服饰纺织": "服装展示画面",
            "家居厨具": "家居生活场景", "日用百货": "生活好物展示",
        }.get(product_type, "产品广告画面")

        # Subject
        product = product_name or "产品"
        textures = vocab.get("textures", ["精致"])
        tex = "、".join(textures[:3])
        subject = (
            f"{product}，{tex}质感，{clean_visual}"
            if clean_visual
            else f"{product}，{tex}质感，画面精致"
        )

        # Action
        action = resolve_segment_action(segment_type, clean_visual)
        # Translate action to Chinese style
        action_cn = self._action_to_chinese(action)

        # Camera
        camera_cn = _CAMERA_KLING.get(camera, _CAMERA_KLING["静态"])

        # Lighting
        lighting = vocab.get("lighting", "柔和的工作室光线")

        # Style tone
        tone_map = {
            "紧迫": "整体色调高对比，充满力度",
            "亲切": "整体色调温暖明快，让人感到舒适",
            "兴奋": "整体色调明亮鲜艳，充满活力",
            "权威": "整体色调沉稳专业",
            "感动": "整体色调温暖怀旧，充满情感",
            "平静": "整体色调柔和清新，宁静舒适",
            "惊讶": "整体色调鲜明，充满视觉冲击",
        }
        tone = tone_map.get(emotion, "整体色调协调悦目")

        # FX adaptation
        fx_map = {
            "震屏": "画面配合轻微震动效果", "闪白": "开头有明亮的闪光过渡",
            "慢动作": "慢动作展示细节", "放大": "画面逐渐放大聚焦",
            "模糊过渡": "边缘柔和的模糊过渡", "无": "",
        }
        fx = fx_map.get(visual_fx, "")

        # Assemble
        prompt = (
            f"{atmosphere}{type_label}。"
            f"{subject}，{action_cn}。"
            f"{camera_cn}，{lighting}。"
            f"{tone}。"
        )
        if fx:
            prompt += f"{fx}。"

        return prompt

    def _action_to_chinese(self, action: str) -> str:
        """Convert English action phrases to Chinese style."""
        action_map = {
            "dramatic reveal": "以一种戏剧性的方式呈现",
            "sudden appearance": "突然出现在画面中",
            "slowly rotating on turntable": "在转盘上缓缓旋转展示",
            "elegantly sliding into frame": "优雅地滑入画面",
            "floating centered in mid-air": "悬浮在画面中央",
            "hero shot with dramatic lighting": "英雄镜头，光影效果突出",
            "being unboxed gracefully": "被优雅地开箱展示",
            "gleaming under studio light": "在工作室灯光下闪闪发光",
        }
        for en, cn in action_map.items():
            if en in action.lower():
                return cn
        return "缓缓展示"  # safe fallback
