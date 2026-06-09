"""Blueprint / Pre-viz storyboard card renderer.

When AI video generation (Seedance/Sora) is unavailable, this module produces
a polished "director's storyboard preview" card instead of a black screen.
The card preserves full audio continuity — TTS/BGM plays while the static
blueprint card fills the screen for the exact segment duration.

Design language: industrial CAD/storyboard aesthetic with grid background,
technical annotations, and cinematography metadata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# ── Color system ──
DARK_BG = "#0D0D1A"
GRID_COLOR = (28, 28, 50)
ACCENT_AMBER = "#FFB300"
ACCENT_GREEN = "#00E676"
TEXT_PRIMARY = "#E8E8ED"
TEXT_SECONDARY = "#8B8B9E"
TEXT_MUTED = "#5A5A72"
DRAFT_BADGE_BG = (255, 179, 0, 40)  # amber tint
CARD_SURFACE = "#141428"
BORDER_DIM = "#2A2A42"

# Segment type → accent color map
TYPE_ACCENT: dict[str, str] = {
    "hook": "#E85D3A",
    "pain": "#8B5CF6",
    "product": "#3B82F6",
    "proof": "#10B981",
    "cta": "#F59E0B",
    "demo": "#06B6D4",
    "offer": "#EF4444",
    "compare": "#8B5CF6",
}

TYPE_LABEL_CN: dict[str, str] = {
    "hook": "开场吸引",
    "pain": "用户痛点",
    "product": "产品展示",
    "proof": "信任背书",
    "cta": "立即行动",
    "demo": "效果演示",
    "offer": "限时优惠",
    "compare": "对比优势",
}

# Camera → Chinese description
CAMERA_CN: dict[str, str] = {
    "静态": "静态锁定机位 · 超稳构图",
    "缓推": "电影级缓推 · 平滑滑轨",
    "快推": "动态快推 · 冲击力聚焦",
    "拉远": "慢拉远 · 宽画幅揭示",
    "横移": "优雅横移 · 水平扫视",
    "跟随": "平滑跟随 · 稳定云台",
    "手持微晃": "手持微晃 · 纪实临场感",
}

# Visual FX → Chinese description
FX_CN: dict[str, str] = {
    "无": "无特效 · 纯写实渲染",
    "震屏": "震屏特效 · 高能冲击",
    "闪白": "闪白过渡 · 高对比度",
    "慢动作": "慢动作 · 120fps升格",
    "放大": "动态放大 · 撞镜变焦",
    "模糊过渡": "电影级模糊过渡",
}


def _load_font(size: int, configured_path: Path | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        configured_path,
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_grid(draw: ImageDraw.Draw, width: int, height: int, step: int = 60) -> None:
    """Draw a subtle engineering grid."""
    for x in range(0, width, step):
        draw.line((x, 0, x, height), fill=GRID_COLOR, width=1)
    for y in range(0, height, step):
        draw.line((0, y, width, y), fill=GRID_COLOR, width=1)
    # Major grid lines every 4 steps
    major = step * 4
    for x in range(0, width, major):
        draw.line((x, 0, x, height), fill=(38, 38, 60), width=1)
    for y in range(0, height, major):
        draw.line((0, y, width, y), fill=(38, 38, 60), width=1)


def _draw_corner_markers(draw: ImageDraw.Draw, width: int, height: int, margin: int = 80) -> None:
    """Draw film-industry corner crop marks (like a director's viewfinder)."""
    arm = 40
    color = (90, 90, 120)
    # Top-left
    draw.line((margin, margin + arm, margin, margin), fill=color, width=2)
    draw.line((margin, margin, margin + arm, margin), fill=color, width=2)
    # Top-right
    draw.line((width - margin - arm, margin, width - margin, margin), fill=color, width=2)
    draw.line((width - margin, margin, width - margin, margin + arm), fill=color, width=2)
    # Bottom-left
    draw.line((margin, height - margin - arm, margin, height - margin), fill=color, width=2)
    draw.line((margin, height - margin, margin + arm, height - margin), fill=color, width=2)
    # Bottom-right
    draw.line((width - margin - arm, height - margin, width - margin, height - margin), fill=color, width=2)
    draw.line((width - margin, height - margin - arm, width - margin, height - margin), fill=color, width=2)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Simple word wrap for Pillow text rendering. Handles CJK characters."""
    if not text.strip():
        return [""]
    lines: list[str] = []
    current: str = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines or [text]


def render_blueprint_card(
    output_path: Path,
    *,
    segment_type: str = "product",
    visual_prompt: str = "",
    script_text: str = "",
    duration: float = 5.0,
    camera: str = "静态",
    visual_fx: str = "无",
    pace: str = "正常",
    emotion: str = "亲切",
    font_path: Path | None = None,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Render a director's storyboard preview card as a PNG.

    Returns the output_path on success.
    """
    accent_hex = TYPE_ACCENT.get(segment_type, ACCENT_AMBER)
    accent_rgb = tuple(int(accent_hex.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

    canvas = Image.new("RGB", (width, height), DARK_BG)
    draw = ImageDraw.Draw(canvas)

    # 1. Grid background (engineering aesthetic)
    _draw_grid(draw, width, height, step=50)
    _draw_corner_markers(draw, width, height, margin=60)

    # 2. Top status bar stripe
    draw.rectangle((0, 0, width, 4), fill=accent_rgb)

    # 3. Top-left: segment type badge
    font_mono_sm = _load_font(28, font_path)
    font_mono_md = _load_font(36, font_path)
    font_large = _load_font(56, font_path)
    font_body = _load_font(42, font_path)
    font_small = _load_font(30, font_path)

    type_label = TYPE_LABEL_CN.get(segment_type, segment_type.upper())
    badge_w = 280
    badge_h = 56
    draw.rounded_rectangle((80, 80, 80 + badge_w, 80 + badge_h), radius=12, fill=CARD_SURFACE, outline=accent_hex, width=2)
    draw.text((80 + badge_w // 2, 80 + badge_h // 2), f"[ {type_label} ]", fill=accent_hex, font=font_mono_md, anchor="mm")

    # 4. Top-right: DRAFT badge
    draft_w = 340
    draft_h = 56
    draw.rounded_rectangle((width - 80 - draft_w, 80, width - 80, 80 + draft_h), radius=12, fill=(255, 179, 0, 35), outline=ACCENT_AMBER, width=2)
    draw.text((width - 80 - draft_w // 2, 80 + draft_h // 2), "◈ AI 生成预留位 / DRAFT", fill=ACCENT_AMBER, font=font_mono_sm, anchor="mm")

    # 5. Center card area — the main storyboard frame
    card_x1, card_y1 = 100, 560
    card_x2, card_y2 = width - 100, 1380
    draw.rounded_rectangle((card_x1, card_y1, card_x2, card_y2), radius=32, fill=CARD_SURFACE, outline=BORDER_DIM, width=2)

    # Inner accent top bar on card
    draw.rectangle((card_x1 + 2, card_y1 + 2, card_x2 - 2, card_y1 + 8), fill=accent_rgb)

    # Aspect ratio guide lines inside card
    guide_inset = 30
    # 9:16 safe area marker
    safe_w = (card_x2 - card_x1 - guide_inset * 2)
    safe_h = int(safe_w * 16 / 9)
    if safe_h > card_y2 - card_y1 - guide_inset * 2:
        safe_h = card_y2 - card_y1 - guide_inset * 2
        safe_w = int(safe_h * 9 / 16)
    safe_x = card_x1 + ((card_x2 - card_x1) - safe_w) // 2
    safe_y = card_y1 + ((card_y2 - card_y1) - safe_h) // 2
    draw.rectangle((safe_x, safe_y, safe_x + safe_w, safe_y + safe_h), outline=(60, 60, 80), width=1)
    # Dashed center cross
    cx = card_x1 + (card_x2 - card_x1) // 2
    cy = card_y1 + (card_y2 - card_y1) // 2
    for i in range(0, 100, 8):
        draw.line((cx - 50 + i, cy, cx - 50 + i + 4, cy), fill=(50, 50, 70), width=1)
        draw.line((cx, cy - 50 + i, cx, cy - 50 + i + 4), fill=(50, 50, 70), width=1)

    # 6. Visual prompt — main content
    visual_text = visual_prompt or script_text or "待填入视觉描述"
    # Clean up production params
    import re
    visual_text = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual_text)
    visual_text = re.sub(r'【[镜字速情视]】', '', visual_text)
    visual_text = re.sub(r'\s+', ' ', visual_text).strip()

    # "VISUAL PROMPT" label
    draw.text((card_x1 + 60, card_y1 + 80), "VISUAL PROMPT / 画面描述", fill=TEXT_MUTED, font=font_mono_sm)

    # Prompt text (wrapped)
    prompt_lines = _wrap_text(f"『 {visual_text} 』", font_large, card_x2 - card_x1 - 120, draw)
    y_offset = card_y1 + 150
    for line in prompt_lines[:4]:  # max 4 lines
        draw.text((card_x1 + 60, y_offset), line, fill=TEXT_PRIMARY, font=font_large)
        y_offset += 70

    # Divider
    draw.line((card_x1 + 60, y_offset + 20, card_x1 + 400, y_offset + 20), fill=accent_hex, width=2)

    # 7. Technical specs grid (bottom section of card)
    spec_y = max(y_offset + 80, card_y2 - 280)
    specs = [
        ("CAMERA / 运镜", CAMERA_CN.get(camera, camera)),
        ("VISUAL FX / 特效", FX_CN.get(visual_fx, visual_fx)),
        ("PACE / 节奏", f"{pace} · BPM {_pace_bpm(pace)}"),
        ("EMOTION / 情绪", emotion),
    ]
    for i, (label, value) in enumerate(specs):
        col = i % 2
        row = i // 2
        sx = card_x1 + 60 + col * 400
        sy = spec_y + row * 80
        draw.text((sx, sy), label, fill=TEXT_MUTED, font=font_mono_sm)
        draw.text((sx, sy + 36), value, fill=TEXT_SECONDARY, font=font_small)

    # 8. Duration indicator bar at bottom of card
    bar_y = card_y2 - 40
    bar_w = card_x2 - card_x1 - 120
    draw.rounded_rectangle((card_x1 + 60, bar_y, card_x1 + 60 + bar_w, bar_y + 6), radius=3, fill=(40, 40, 60))
    fill_w = int(bar_w * 0.35)  # AIGC segments typically 30-40% progress look
    if fill_w > 0:
        draw.rounded_rectangle((card_x1 + 60, bar_y, card_x1 + 60 + fill_w, bar_y + 6), radius=3, fill=accent_rgb)
    draw.text((card_x1 + 60, bar_y - 30), f"DURATION: {duration:.1f}s", fill=TEXT_MUTED, font=font_mono_sm)

    # 9. Bottom tech footer
    footer_y = card_y2 + 60
    draw.line((100, footer_y - 10, width - 100, footer_y - 10), fill=(30, 30, 50), width=1)
    footer_text = "StructForge Blueprint Engine v2.0  |  Pre-viz Render  |  Insert API Key to unlock real-time AI video"
    draw.text((width // 2, footer_y), footer_text, fill=TEXT_MUTED, font=font_mono_sm, anchor="ma")
    draw.text((width // 2, footer_y + 40), "帧率: 30fps  |  编码: H.264  |  色彩: Rec.709  |  画幅: 9:16", fill=(50, 50, 70), font=_load_font(22, font_path), anchor="ma")

    # 10. Side margin technical tick marks
    for y in range(200, height - 200, 100):
        tick_len = 20 if y % 400 == 0 else 10
        draw.line((40, y, 40 + tick_len, y), fill=(60, 60, 80), width=1)
        draw.line((width - 40, y, width - 40 - tick_len, y), fill=(60, 60, 80), width=1)
        if y % 400 == 0:
            time_at_y = round((y - 200) / (height - 400) * duration, 1)
            draw.text((20, y), f"{time_at_y:.1f}s", fill=(50, 50, 70), font=_load_font(18, font_path), anchor="rm")

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", quality=95)
    return output_path


def _pace_bpm(pace: str) -> int:
    return {"快": 140, "正常": 120, "慢": 100}.get(pace, 120)


# ── Blueprint Payload (for frontend preview) ──

@dataclass
class BlueprintPayload:
    """Data sent to frontend for the API payload preview drawer."""
    segment_id: str
    segment_type: str
    segment_label: str
    duration: float
    visual_prompt: str
    script_text: str
    camera: str = "静态"
    visual_fx: str = "无"
    pace: str = "正常"
    emotion: str = "亲切"
    # API call params for preview
    model: str = "doubao-seedance-2-0-260128"
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    api_provider: str = "Volcano Ark / Seedance"
    is_available: bool = False
    # Full JSON payload that would be sent
    api_payload: dict[str, Any] = field(default_factory=dict)


def build_blueprint_payload(segment: Any, api_key_available: bool = False) -> BlueprintPayload:
    """Build a BlueprintPayload from a segment for frontend preview."""
    import re
    visual = getattr(segment, 'visual', '') or getattr(segment, 'script', '') or ''
    visual = re.sub(r'【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?', '', visual)
    visual = re.sub(r'【[镜字速情视]】', '', visual)
    visual = re.sub(r'\s+', ' ', visual).strip()

    camera = getattr(segment, 'camera', '静态')
    visual_fx = getattr(segment, 'visual_fx', '无')
    pace = getattr(segment, 'pace', '正常')
    emotion = getattr(segment, 'emotion', '亲切')
    duration = float(getattr(segment, 'duration', 5))

    # ── Precise Token & Cost Estimation ──
    # Seedance 2.0 processes at 30fps and bills per effective frame.
    # The coefficient 0.8 accounts for keyframe efficiency (not every frame
    # costs a full token — motion interpolation reuses adjacent frames).
    # Cost basis: ~$0.0003 per effective frame at 720p.
    fps = 30
    frame_eff_coefficient = 0.8  # keyframe sampling ratio
    est_tokens = int(duration * fps * frame_eff_coefficient)
    # per-frame cost * effective frames
    est_cost = round(duration * fps * frame_eff_coefficient * 0.0003, 3)
    if est_cost < 0.01:
        est_cost = 0.01  # minimum billing unit

    prompt_text = f"Commercial advertisement, 9:16, shot on Arri Alexa 65. {visual}. Camera: {camera}. FX: {visual_fx}."

    payload = {
        "model": "doubao-seedance-2-0-260128",
        "content": [{"type": "text", "text": prompt_text}],
        "duration": max(4, min(int(duration), 12)),
        "ratio": "9:16",
        "resolution": "720p",
        "watermark": False,
    }

    return BlueprintPayload(
        segment_id=getattr(segment, 'id', ''),
        segment_type=getattr(segment, 'type', 'product'),
        segment_label=getattr(segment, 'label', ''),
        duration=duration,
        visual_prompt=visual,
        script_text=getattr(segment, 'script', '') or '',
        camera=camera,
        visual_fx=visual_fx,
        pace=pace,
        emotion=emotion,
        estimated_tokens=est_tokens,
        estimated_cost_usd=est_cost,
        api_provider="Volcano Ark / Seedance 2.0",
        is_available=api_key_available,
        api_payload=payload,
    )
