"""Template discovery and management utility — Pixelle-Video pattern.

Provides template discovery, type detection, media size parsing,
and resource override system (data/templates/ > templates/).

Usage:
    templates = list_templates()
    path = resolve_template_path("prompt_card")
    w, h = parse_template_size(path)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

# ── Template directories (resource override: data/ > default) ──
SERVICE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SERVICE_ROOT / "templates"
DATA_TEMPLATE_DIR = SERVICE_ROOT / "data" / "templates"  # User custom overrides

# ── Type detection by filename prefix ──
# Mirrors Pixelle-Video's get_template_type() convention.
# image_* = needs image generation (ComfyUI or Prompt Card)
# static_* = pure text/design, no media generation needed
# video_* = needs video generation

def get_template_type(name: str) -> Literal["image", "static", "video"]:
    """Detect template type from filename prefix."""
    if name.startswith("static_"):
        return "static"
    if name.startswith("video_"):
        return "video"
    return "image"  # default


def list_templates() -> list[dict]:
    """List all available HTML templates with metadata.

    Custom templates in data/templates/ take priority over defaults.
    """
    seen: set[str] = set()
    templates: list[dict] = []

    # Scan data/templates/ first (higher priority)
    for dir_path in [DATA_TEMPLATE_DIR, TEMPLATE_DIR]:
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("*.html")):
            if f.stem in seen:
                continue
            seen.add(f.stem)
            source = "custom" if dir_path == DATA_TEMPLATE_DIR else "default"
            templates.append({
                "name": f.stem,
                "path": str(f),
                "type": get_template_type(f.name),
                "filename": f.name,
                "source": source,
            })
    return templates


def resolve_template_path(template_ref: str) -> Path:
    """Resolve a template reference to an absolute path.

    Checks data/templates/ first (user custom), then templates/ (default).
    Supports: 'prompt_card' → data/templates/prompt_card.html or templates/prompt_card.html
              'product_hero' → same
              'templates/prompt_card.html' → absolute path
    """
    if template_ref.endswith(".html"):
        name = template_ref.replace(".html", "").split("/")[-1]
    else:
        name = template_ref

    # Check data/templates/ first (user custom override)
    for dir_path in [DATA_TEMPLATE_DIR, TEMPLATE_DIR]:
        candidate = dir_path / f"{name}.html"
        if candidate.exists():
            return candidate

    # Check absolute path
    abs_candidate = Path(template_ref)
    if abs_candidate.exists():
        return abs_candidate

    # Fallback to default
    fallback = TEMPLATE_DIR / "prompt_card.html"
    if fallback.exists():
        return fallback

    raise FileNotFoundError(f"Template not found: {template_ref}")


def parse_template_size(template_path: str | Path) -> tuple[int, int]:
    """Parse media width/height from template meta tags.

    Reads <meta name="template:media-width" content="1080">
          <meta name="template:media-height" content="1920">

    Falls back to 1080x1920 if not specified.
    """
    path = Path(template_path) if isinstance(template_path, str) else template_path
    width, height = 1080, 1920

    if not path.exists():
        return width, height

    try:
        content = path.read_text(encoding="utf-8")
        w_match = re.search(r'<meta\s+name="template:media-width"\s+content="(\d+)"', content)
        h_match = re.search(r'<meta\s+name="template:media-height"\s+content="(\d+)"', content)
        if w_match:
            width = int(w_match.group(1))
        if h_match:
            height = int(h_match.group(1))
    except Exception:
        pass

    return width, height


def get_template_for_segment(segment_type: str) -> str:
    """Recommend a template based on segment type."""
    type_templates = {
        "hook": "prompt_card",
        "pain": "prompt_card",
        "product": "product_hero",
        "proof": "prompt_card",
        "cta": "prompt_card",
    }
    name = type_templates.get(segment_type, "prompt_card")

    template_path = TEMPLATE_DIR / f"{name}.html"
    if template_path.exists():
        return str(template_path)
    return str(TEMPLATE_DIR / "prompt_card.html")
