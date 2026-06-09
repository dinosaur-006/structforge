"""Product-category adaptive vocabulary for text-to-video prompt generation.

Maps product types → visual vocabulary (subjects, actions, textures, lighting)
and emotions → camera parameters. Used by PromptAssembler to translate abstract
segment metadata into concrete, platform-appropriate visual descriptions.
"""

from __future__ import annotations

from typing import Any

# ══════════════════════════════════════════════════════════════════════════
# Product category → visual vocabulary
# ══════════════════════════════════════════════════════════════════════════

PRODUCT_VOCABULARY: dict[str, dict[str, dict[str, Any]]] = {
    "食品饮料": {
        "液体类": {
            "subjects": ["beverage", "drink", "liquid", "bottle", "glass", "can"],
            "actions": ["pouring smoothly", "swirling gently", "bubbling naturally", "steaming freshly", "dripping slowly"],
            "textures": ["glossy", "sparkling", "golden", "crystal-clear", "foamy", "refreshing"],
            "lighting": "warm natural sunlight, shallow depth of field, appetizing color grade, food photography lighting",
            "camera_preference": "缓推",
        },
        "零食类": {
            "subjects": ["snack", "crispy sticks", "bites", "pieces", "chips"],
            "actions": ["being picked up", "being bitten into", "scattered on rustic surface", "being dipped in sauce"],
            "textures": ["crispy", "crunchy", "golden-brown", "flaky", "glazed", "spicy-red", "sesame-speckled"],
            "lighting": "warm vibrant colors, food photography lighting, glossy highlights, steam particles",
            "camera_preference": "快推",
        },
        "乳制品": {
            "subjects": ["milk", "yogurt", "cream", "cheese", "dairy product"],
            "actions": ["swirling in glass", "being poured smoothly", "being spread evenly", "slowly dripping"],
            "textures": ["creamy", "smooth", "white", "fresh", "thick", "velvety"],
            "lighting": "soft morning light, pure white background, clean aesthetic, subtle reflections",
            "camera_preference": "缓推",
        },
        "调味品": {
            "subjects": ["sauce bottle", "condiment jar", "spice container", "oil dispenser"],
            "actions": ["being drizzled over food", "being sprinkled evenly", "steam rising from dish"],
            "textures": ["glossy", "viscous", "granular", "golden-red", "dark-rich"],
            "lighting": "warm kitchen light, close-up food styling, appetizing amber tones",
            "camera_preference": "横移",
        },
    },
    "美妆护肤": {
        "膏体类": {
            "subjects": ["cream", "balm", "ointment", "paste", "moisturizer"],
            "actions": ["being squeezed from tube", "being scooped with spatula", "being applied smoothly", "melting on skin"],
            "textures": ["pearly", "velvety", "smooth", "rich", "whipped", "silky"],
            "lighting": "soft diffused beauty light, pearl-like reflections, clean white background",
            "camera_preference": "缓推",
        },
        "液体类": {
            "subjects": ["serum", "essence", "toner", "oil", "liquid foundation"],
            "actions": ["dripping from glass dropper", "spreading on surface", "being absorbed instantly", "gleaming under light"],
            "textures": ["transparent", "golden", "viscous", "lightweight", "watery", "radiant"],
            "lighting": "soft backlight, glass reflections, clean minimal background, diamond-like sparkle",
            "camera_preference": "静态",
        },
        "粉末类": {
            "subjects": ["loose powder", "setting powder", "blush", "highlighter"],
            "actions": ["being brushed on gently", "fine particles floating in light", "swirling in air"],
            "textures": ["fine", "silky", "shimmering", "light-as-air", "soft-focus"],
            "lighting": "soft ring light, ethereal glow, dreamy bokeh background",
            "camera_preference": "缓推",
        },
    },
    "电子3C": {
        "手机/平板": {
            "subjects": ["smartphone", "tablet", "mobile device", "screen"],
            "actions": ["screen lighting up brilliantly", "being held elegantly", "being swiped smoothly", "edge-to-edge display glowing"],
            "textures": ["metallic", "glossy", "edge-to-edge", "sleek", "premium", "ultra-thin"],
            "lighting": "cool blue accent rim light, dark reflective surface, futuristic studio",
            "camera_preference": "环绕",
        },
        "耳机/音响": {
            "subjects": ["earbuds", "headphones", "speaker", "audio device"],
            "actions": ["floating in mid-air", "being worn naturally", "LED indicator pulsing softly", "rotating slowly"],
            "textures": ["matte", "brushed metal", "silicone", "premium", "compact", "ergonomic"],
            "lighting": "dark moody studio, subtle edge glow, tech-inspired atmosphere, clean reflections",
            "camera_preference": "环绕",
        },
        "可穿戴": {
            "subjects": ["smartwatch", "fitness tracker", "wearable device"],
            "actions": ["being worn on wrist", "display lighting up", "rotating on turntable", "haptic feedback pulse"],
            "textures": ["brushed steel", "sapphire glass", "silicone band", "premium finish"],
            "lighting": "soft studio key light, controlled reflections, luxury product aesthetic",
            "camera_preference": "缓推",
        },
    },
    "服饰纺织": {
        "面料类": {
            "subjects": ["fabric", "textile", "cloth", "garment material"],
            "actions": ["draped elegantly", "flowing in gentle breeze", "being touched lightly", "folding naturally"],
            "textures": ["soft", "breathable", "textured", "flowing", "natural folds", "fine weave"],
            "lighting": "natural window light, soft shadows, organic warm tones",
            "camera_preference": "横移",
        },
        "成衣类": {
            "subjects": ["clothing item", "outfit", "garment", "apparel piece"],
            "actions": ["being worn confidently", "being displayed on mannequin", "fabric flowing gracefully"],
            "textures": ["tailored", "structured", "flowing", "premium fabric", "detailed stitching"],
            "lighting": "fashion studio lighting, clean backdrop, editorial aesthetic",
            "camera_preference": "跟随",
        },
    },
    "家居厨具": {
        "器皿类": {
            "subjects": ["ceramic mug", "glassware", "cookware", "kitchen tool"],
            "actions": ["being used naturally", "catching morning light", "sitting on rustic wooden surface"],
            "textures": ["matte ceramic", "clear glass", "brushed steel", "handcrafted", "glazed"],
            "lighting": "warm morning kitchen light, cozy atmosphere, practical elegance",
            "camera_preference": "静态",
        },
        "家具类": {
            "subjects": ["furniture piece", "home decor", "interior element"],
            "actions": ["standing elegantly in room", "catching sunlight through window", "being styled naturally"],
            "textures": ["solid wood grain", "smooth lacquer", "soft upholstery", "natural material"],
            "lighting": "natural daylight through window, warm ambient glow, interior design aesthetic",
            "camera_preference": "拉远",
        },
    },
    "日用百货": {
        "默认": {
            "subjects": ["everyday product", "household item", "daily essential"],
            "actions": ["being demonstrated clearly", "sitting on clean surface", "being used practically"],
            "textures": ["clean", "practical", "well-designed", "modern", "durable"],
            "lighting": "bright clean studio light, practical product photography, neutral background",
            "camera_preference": "静态",
        },
    },
    "其他": {
        "默认": {
            "subjects": ["product", "item", "merchandise"],
            "actions": ["being displayed prominently", "rotating slowly", "centered in frame"],
            "textures": ["clean", "professional", "well-lit"],
            "lighting": "studio lighting, clean background, commercial photography",
            "camera_preference": "静态",
        },
    },
}


def resolve_product_vocab(product_type: str, visual_hint: str = "") -> dict[str, Any]:
    """Find the best-matching vocabulary entry for a product type.

    Falls back through: exact match → broad category → "其他/默认".
    """
    category = PRODUCT_VOCABULARY.get(product_type)
    if category:
        # Try to match a sub-category from visual hint
        for sub_key, sub_vocab in category.items():
            if sub_key != "默认":
                keywords = sub_vocab.get("subjects", [])
                if any(kw in visual_hint.lower() for kw in keywords):
                    return sub_vocab
        # Return first non-default sub-category, or default
        for sub_key in category:
            if sub_key != "默认":
                return category[sub_key]
        return category.get("默认", _default_vocab())

    # Broad category fallback: try partial match
    for cat_key in PRODUCT_VOCABULARY:
        if cat_key in product_type or product_type in cat_key:
            cat = PRODUCT_VOCABULARY[cat_key]
            return cat.get(list(cat.keys())[0], _default_vocab())

    return _default_vocab()


def _default_vocab() -> dict[str, Any]:
    return PRODUCT_VOCABULARY["其他"]["默认"]


# ══════════════════════════════════════════════════════════════════════════
# Emotion → camera + FX mapping
# ══════════════════════════════════════════════════════════════════════════

EMOTION_CAMERA_MAP: dict[str, dict[str, str]] = {
    "紧迫": {"camera": "快推", "speed": "fast", "fx": "震屏",
             "style_tone": "high contrast, urgent energy, dramatic spotlight"},
    "惊讶": {"camera": "快推", "speed": "fast", "fx": "闪白",
             "style_tone": "shock value, bright flash, heightened contrast"},
    "兴奋": {"camera": "快推", "speed": "medium", "fx": "放大",
             "style_tone": "vibrant energy, dynamic motion, celebratory light"},
    "亲切": {"camera": "缓推", "speed": "slow", "fx": "无",
             "style_tone": "warm and inviting, soft natural light, gentle approach"},
    "权威": {"camera": "静态", "speed": "static", "fx": "无",
             "style_tone": "professional confidence, clean lighting, authoritative presence"},
    "感动": {"camera": "拉远", "speed": "slow", "fx": "慢动作",
             "style_tone": "emotional pull-back, warm nostalgic tone, soft vignette"},
    "平静": {"camera": "横移", "speed": "slow", "fx": "模糊过渡",
             "style_tone": "calm atmosphere, gentle movement, soothing color palette"},
}


# ══════════════════════════════════════════════════════════════════════════
# Segment type → default action suggestions
# ══════════════════════════════════════════════════════════════════════════

SEGMENT_ACTION_HINTS: dict[str, list[str]] = {
    "hook": [
        "dramatic reveal", "sudden appearance", "eye-catching entrance",
        "bursting into frame with energy", "striking close-up impact",
        "spinning into view", "exploding with particles",
    ],
    "pain": [
        "mundane problem scenario", "struggling with inconvenience",
        "looking frustrated", "dealing with messy situation",
    ],
    "product": [
        "slowly rotating on turntable", "elegantly sliding into frame",
        "floating centered in mid-air", "hero shot with dramatic lighting",
        "being unboxed gracefully", "gleaming under studio light",
    ],
    "proof": [
        "side-by-side comparison", "data visualization overlay",
        "before-and-after reveal", "macro close-up of test result",
        "demonstration in controlled environment",
    ],
    "cta": [
        "limited-time offer card appearing", "discount badge bursting in",
        "purchase button glowing invitingly", "countdown timer ticking",
        "gift box stacking up", "shopping cart filling up",
    ],
}


def resolve_segment_action(segment_type: str, visual_hint: str = "") -> str:
    """Return an action description appropriate for the segment type."""
    import random
    hints = SEGMENT_ACTION_HINTS.get(segment_type, SEGMENT_ACTION_HINTS["product"])
    # Try to pick a hint that relates to the visual description
    if visual_hint:
        for hint in hints:
            words = set(hint.lower().split())
            vis_words = set(visual_hint.lower().split())
            if len(words & vis_words) >= 2:
                return hint
    return hints[hash(segment_type + visual_hint) % len(hints)]


# ══════════════════════════════════════════════════════════════════════════
# Seedance-specific style vocabulary
# ══════════════════════════════════════════════════════════════════════════

SEEDANCE_STYLE_PRESETS: dict[str, str] = {
    "商业广告": "volumetric studio lighting, Arri Alexa 65, hyper-realistic 8k resolution, masterpiece, exquisite detail",
    "自然清新": "natural daylight, soft shadows, organic color palette, subtle film grain, airy atmosphere",
    "高级质感": "cinematic anamorphic lens, controlled reflections, subtle vignette, 35mm film look, premium texture",
    "食欲满满": "warm vibrant colors, food photography lighting, visible steam particles, glossy highlights, mouth-watering appeal",
    "科技未来": "cool blue tones, clean minimal background, glass reflections, sci-fi product ambiance, sleek modern",
    "温馨治愈": "warm golden hour light, soft bokeh, cozy atmosphere, gentle glow, nostalgic film aesthetic",
    "时尚潮流": "editorial fashion lighting, bold colors, sharp contrast, magazine cover aesthetic, trendy vibe",
}


def resolve_style_tone(emotion: str, product_type: str = "") -> str:
    """Map emotion → Seedance style preset, with product-type override."""
    # Product-type overrides
    product_style = {
        "食品饮料": "食欲满满",
        "美妆护肤": "高级质感",
        "电子3C": "科技未来",
        "服饰纺织": "时尚潮流",
        "家居厨具": "温馨治愈",
    }
    tone = product_style.get(product_type)
    if tone and tone in SEEDANCE_STYLE_PRESETS:
        return SEEDANCE_STYLE_PRESETS[tone]

    # Emotion-based fallback
    emotion_tone = {
        "紧迫": "商业广告",
        "惊讶": "商业广告",
        "兴奋": "商业广告",
        "亲切": "温馨治愈",
        "权威": "高级质感",
        "感动": "温馨治愈",
        "平静": "自然清新",
    }
    tone = emotion_tone.get(emotion, "商业广告")
    return SEEDANCE_STYLE_PRESETS.get(tone, SEEDANCE_STYLE_PRESETS["商业广告"])
