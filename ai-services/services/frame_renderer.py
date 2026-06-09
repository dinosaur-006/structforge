"""HTML-based frame renderer using Playwright.

Renders HTML+CSS templates to PNG frames for FFmpeg video composition.
Replaces FFmpeg drawtext/eq/crop filter chains — any CSS animation works,
zero FFmpeg expression parsing bugs (no more sin/crop crashes).

Ported from Pixelle-Video's frame_html.py (Apache 2.0).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


class FrameRenderer:
    """Render HTML+CSS templates to PNG frames via Playwright.

    Falls back to None if Playwright is not installed. Caller should use
    Pillow-based render_blueprint_card() as a backup.

    Usage:
        renderer = FrameRenderer("templates/prompt_card.html")
        path = renderer.render(text="Prompt text", output="output.png")
    """

    _browser = None
    _playwright = None

    def __init__(self, template_path: str | Path) -> None:
        self.template_path = str(template_path)
        self.template = self._load_template(template_path)
        self._available = False
        try:
            from playwright.sync_api import sync_playwright
            self._sync_playwright = sync_playwright
            self._available = True
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self._available

    def _load_template(self, path: str | Path) -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return p.read_text(encoding="utf-8")

    def render(
        self,
        *,
        prompt_text: str = "",
        subtitle_text: str = "",
        camera: str = "静态",
        visual_fx: str = "无",
        duration: float = 5.0,
        emotion: str = "亲切",
        cost: float = 0.0,
        output_path: str = "",
        width: int = 1080,
        height: int = 1920,
    ) -> str | None:
        """Render HTML template to PNG. Returns output path or None on failure."""
        if not self._available:
            return None

        try:
            html = (
                self.template
                .replace("{{prompt_text}}", str(prompt_text)[:500])
                .replace("{{subtitle_text}}", str(subtitle_text)[:200])
                .replace("{{camera}}", str(camera))
                .replace("{{visual_fx}}", str(visual_fx))
                .replace("{{duration}}", f"{duration:.1f}")
                .replace("{{emotion}}", str(emotion))
                .replace("{{cost}}", f"{cost:.3f}")
            )

            out = output_path or tempfile.mktemp(suffix=".png", prefix="pv_frame_")
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

            with self._sync_playwright() as p:
                browser = p.chromium.launch(
                    args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
                )
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=out, type="png", omit_background=True)
                page.close()
                browser.close()

            if Path(out).exists() and Path(out).stat().st_size > 100:
                return out
            return None
        except Exception:
            return None


def _render_prompt_card_html(
    *,
    prompt_text: str = "",
    subtitle_text: str = "",
    camera: str = "静态",
    visual_fx: str = "无",
    duration: float = 5.0,
    emotion: str = "亲切",
    cost: float = 0.0,
) -> str | None:
    """Convenience: render prompt card via HTML template (Playwright)."""
    renderer = FrameRenderer("templates/prompt_card.html")
    if not renderer.available:
        return None
    return renderer.render(
        prompt_text=prompt_text, subtitle_text=subtitle_text,
        camera=camera, visual_fx=visual_fx,
        duration=duration, emotion=emotion, cost=cost,
    )
