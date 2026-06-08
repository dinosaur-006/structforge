"""Phase 5: LUT color grading with product color protection."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

LUT_MAP = {
    "自然通透": "natural_clear",
    "电影质感": "film_look",
    "清新明亮": "fresh_bright",
    "高对比度": "high_contrast",
    "原片风格": "original_style",
}


def recommend_lut(dominant_colors: list[str], product_type: str = "") -> str:
    """Recommend LUT preset based on dominant colors and product type."""
    warm = sum(1 for c in dominant_colors if any(w in str(c).lower() for w in ("red", "orange", "yellow", "gold", "warm", "brown")))
    cool = sum(1 for c in dominant_colors if any(c2 in str(c).lower() for c2 in ("blue", "cyan", "teal", "cool", "green")))
    if product_type in ("electronics", "3c", "科技"):
        return "高对比度"
    if warm > cool:
        return "电影质感"
    if cool > warm:
        return "清新明亮"
    return "自然通透"


def apply_lut(
    input_path: str | Path,
    lut_name: str,
    output_path: str | Path | None = None,
    protect_product_color: bool = False,
    has_product: bool = False,
) -> str:
    """Apply LUT via FFmpeg, optionally with product color protection."""
    inp = Path(input_path)
    out = Path(output_path or inp.parent / f"{inp.stem}_lut{inp.suffix}")

    lut_key = LUT_MAP.get(lut_name, "natural_clear")
    lut_file = Path(__file__).parent.parent / "presets" / f"{lut_key}.cube"

    vf = f"lut3d={lut_file}" if lut_file.exists() else "eq=contrast=1.02:saturation=1.02"
    if protect_product_color and has_product:
        vf += ",colorbalance=rs=-0.02:gs=-0.02:bs=-0.02"

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", vf, "-c:a", "copy", str(out)],
        capture_output=True, check=False,
    )
    return str(out) if out.exists() else str(inp)
