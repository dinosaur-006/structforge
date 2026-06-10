"""Phase 7: FFmpeg-internal animation enhancement.

Generates animated text/overlay WebM clips with alpha channel using Pillow + FFmpeg.
No external Node.js/Chromium dependency — pure Python.

Animation types: fade_in_up, pop_in, typewriter, pulse_glow, count_up
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFont

AnimationType = Literal["fade_in_up", "pop_in", "typewriter", "pulse_glow"]

DEFAULT_FONT_PATHS = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in DEFAULT_FONT_PATHS:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def create_animated_overlay(
    text: str,
    output_dir: str | Path | None = None,
    *,
    duration: float = 2.0,
    fps: int = 30,
    animation: AnimationType = "fade_in_up",
    width: int = 1080,
    height: int = 1920,
    font_size: int = 64,
    text_color: tuple[int, int, int] = (255, 255, 255),
    bg_start: tuple[int, int, int, int] = (0, 0, 0, 0),
    bg_end: tuple[int, int, int, int] = (0, 0, 0, 180),
    position: tuple[float, float] = (0.5, 0.85),  # relative x, y center
    glow_color: tuple[int, int, int] | None = None,
    ffmpeg_path: str = "ffmpeg",
) -> str | None:
    """Generate an animated overlay WebM with alpha channel.

    Returns the path to the .webm file, or None on failure.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "_frames"
    frames_dir.mkdir(exist_ok=True)

    total_frames = max(1, int(duration * fps))
    font = _load_font(font_size)
    center_x = int(width * position[0])
    center_y = int(height * position[1])

    for frame_i in range(total_frames):
        t = frame_i / max(total_frames - 1, 1)  # 0.0 → 1.0
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # Background gradient
        bg_alpha = int(bg_start[3] + (bg_end[3] - bg_start[3]) * t)
        if bg_alpha > 0:
            r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * t)
            g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * t)
            b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * t)
            overlay_bg = Image.new("RGBA", (width, height), (r, g, b, bg_alpha))
            canvas = Image.alpha_composite(canvas, overlay_bg)
            draw = ImageDraw.Draw(canvas)

        # Text animation
        alpha, offset_y, scale = _anim_params(animation, t)

        if animation == "typewriter":
            visible_chars = max(1, int(len(text) * t * 1.3))
            display_text = text[:visible_chars]
        else:
            display_text = text

        if alpha > 0 and display_text:
            # Render text to a temp image at scale
            tw, th = _text_size(display_text, font)
            scaled_w = int(tw * scale)
            scaled_h = int(th * scale)
            if scaled_w > 0 and scaled_h > 0:
                txt_img = Image.new("RGBA", (scaled_w + 20, scaled_h + 20), (0, 0, 0, 0))
                txt_draw = ImageDraw.Draw(txt_img)
                txt_draw.text((10, 10), display_text, fill=(*text_color, int(255 * alpha)), font=font)
                if scaled_w != tw:
                    txt_img = txt_img.resize((scaled_w, scaled_h), Image.LANCZOS)

                paste_x = center_x - scaled_w // 2
                paste_y = center_y - scaled_h // 2 + int(offset_y)
                canvas.paste(txt_img, (paste_x, paste_y), txt_img)

        # Glow effect (pulse)
        if glow_color:
            glow_alpha = int(abs((t * 2) % 2 - 1) * 80)  # pulse 0→80→0
            glow = Image.new("RGBA", (width, height), (*glow_color, glow_alpha))
            canvas = Image.alpha_composite(canvas, glow)

        frame_path = frames_dir / f"frame_{frame_i:05d}.png"
        canvas.save(frame_path, "PNG")

    # Encode frames to WebM with alpha
    output_path = out_dir / f"overlay_{hash(text) & 0xFFFF:04x}.webm"
    cmd = [
        ffmpeg_path, "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",
        "-t", f"{duration:.3f}",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception:
        shutil.rmtree(frames_dir, ignore_errors=True)
        return None

    # Cleanup frames
    import shutil
    shutil.rmtree(frames_dir, ignore_errors=True)

    return str(output_path) if output_path.exists() else None


def _anim_params(anim: str, t: float) -> tuple[float, float, float]:
    """Return (alpha, offset_y, scale) for a given animation type at time t."""
    if anim == "fade_in_up":
        alpha = min(1.0, t * 3)  # fast fade
        offset_y = max(-20, (1 - t) * -20)  # move up from below
        scale = 1.0
    elif anim == "pop_in":
        # Spring-like: overshoot then settle
        if t < 0.3:
            alpha = t / 0.3
            scale = 0.5 + 0.7 * (t / 0.3)
        elif t < 0.5:
            alpha = 1.0
            scale = 1.2 - 0.2 * ((t - 0.3) / 0.2)
        else:
            alpha = 1.0
            scale = 1.0
        offset_y = 0
    elif anim == "typewriter":
        alpha = 1.0
        offset_y = 0
        scale = 1.0
    elif anim == "pulse_glow":
        alpha = 1.0
        offset_y = 0
        scale = 0.95 + 0.05 * (abs((t * 3) % 2 - 1))  # subtle pulse
    else:
        alpha = 1.0
        offset_y = 0
        scale = 1.0
    return alpha, offset_y, scale


def _text_size(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int]:
    """Get text bounding box size."""
    bbox = font.getbbox(text)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])
