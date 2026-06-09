"""Platform-specific negative prompts for text-to-video generation.

Rule: select only 3-5 most relevant items. Stacking ALL negatives blurs the output.
Each platform has different sensitivities — what works for Seedance may not work for Runway.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════
# Universal negatives (safe for all platforms, always include 2-3)
# ══════════════════════════════════════════════════════════════════════════

UNIVERSAL_NEGATIVES: list[str] = [
    "no text overlays",
    "no watermarks",
    "no logos",
    "no warped objects",
    "no melting edges",
]

# ══════════════════════════════════════════════════════════════════════════
# Platform-specific negatives
# ══════════════════════════════════════════════════════════════════════════

SEEDANCE_NEGATIVES: dict[str, list[str]] = {
    "camera": [
        "no snap zooms",
        "no whip pans",
        "no Dutch angles",
        "no jump cuts",
    ],
    "lighting": [
        "no neon lighting",
        "no heavy teal/orange color grade",
        "no cartoon saturation",
        "no lens flares",
    ],
    "product": [
        "keep product shape consistent",
        "no morphing",
        "no distorted labels",
        "no extra reflections on product surface",
    ],
    "general": [
        "no extra fingers",
        "no deformed hands",
        "no crowd",
        "no mirrors reflecting other people",
        "no floating UI elements",
    ],
}

RUNWAY_NEGATIVES: dict[str, list[str]] = {
    "camera": [
        "stable lighting",
        "no exposure flicker",
        "single continuous shot",
    ],
    "product": [
        "keep reflections clean",
        "no refraction wobble",
        "no speed ramps",
    ],
    "general": [
        "no text in scene",
        "no brand logos",
        "no extra characters",
        "natural skin tones",
    ],
}

KLING_NEGATIVES: dict[str, list[str]] = {
    "camera": [
        "画面稳定不抖动",
    ],
    "lighting": [
        "光线自然不要过度曝光",
        "不要出现奇怪的光影",
    ],
    "product": [
        "物体形状保持一致不变形",
    ],
    "general": [
        "人物形象保持一致不变形",
        "不要出现文字和水印",
        "背景简洁不杂乱",
        "画面清晰不模糊",
    ],
}


def select_negatives(
    platform: str,
    *,
    visual_fx: str = "无",
    segment_type: str = "product",
    include_product: bool = True,
) -> str:
    """Select 3-5 optimal negative prompts for the given platform and context.

    Selection strategy:
    1. Always include 2 universal negatives
    2. Select 1-2 from platform-specific camera category
    3. If product-focused, add 1 product-specific negative
    4. Total: 3-5 items
    """
    platform_negatives = {
        "seedance": SEEDANCE_NEGATIVES,
        "runway": RUNWAY_NEGATIVES,
        "kling": KLING_NEGATIVES,
    }.get(platform, SEEDANCE_NEGATIVES)

    selected: list[str] = []

    # 2 universal negatives (rotate selection based on segment hash)
    base = hash(segment_type) % len(UNIVERSAL_NEGATIVES)
    selected.append(UNIVERSAL_NEGATIVES[base])
    selected.append(UNIVERSAL_NEGATIVES[(base + 2) % len(UNIVERSAL_NEGATIVES)])

    # 1-2 camera negatives
    camera_negs = platform_negatives.get("camera", [])
    if camera_negs:
        idx = hash(visual_fx + segment_type) % len(camera_negs)
        selected.append(camera_negs[idx])

    # 1 product negative (if applicable)
    if include_product:
        product_negs = platform_negatives.get("product", [])
        if product_negs:
            idx = hash(segment_type) % len(product_negs)
            selected.append(product_negs[idx])

    # 1 general negative (rotate)
    general_negs = platform_negatives.get("general", [])
    if general_negs:
        idx = (hash(visual_fx) + hash(segment_type)) % len(general_negs)
        selected.append(general_negs[idx])

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in selected:
        if s.lower() not in seen:
            seen.add(s.lower())
            unique.append(s)

    return ", ".join(unique[:5])
