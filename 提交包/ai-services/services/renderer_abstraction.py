"""Renderer Abstraction Layer — pluggable video rendering engines.

Provides a unified interface so Remotion, Pillow/FFmpeg, and future
renderers are interchangeable. The factory auto-detects the best
available engine at startup.

Engines:
  - RemotionRenderer  — high-fidelity spring animations (Node.js microservice)
  - PillowRenderer    — lightweight, zero-dependency fallback (always available)

Usage:
    renderer = RendererFactory.create(settings)
    path = renderer.render_cta(price="99.9", slogan="限时优惠")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── Abstract Protocol ──

class VideoRenderer(ABC):
    """Abstract renderer for animated video overlays."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name for status display."""
        ...

    @abstractmethod
    def available(self) -> bool:
        """Whether this renderer can fulfil requests right now."""
        ...

    @abstractmethod
    def render_cta(
        self,
        price: str,
        slogan: str = "",
        original_price: str | None = None,
        primary_color: str = "#FFD700",
        output_dir: str | Path | None = None,
        duration: float = 3.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        """Render CTA spring animation. Returns (path, fallback_reason)."""
        ...

    @abstractmethod
    def render_hook(
        self,
        keyword: str,
        emotion: str = "震惊",
        output_dir: str | Path | None = None,
        duration: float = 2.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        """Render hook bounce animation. Returns (path, fallback_reason)."""
        ...

    def render_for_segment(
        self,
        segment_type: str,
        script_text: str,
        output_dir: str | Path | None = None,
        duration: float = 2.5,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        """Convenience: route to render_cta or render_hook based on segment_type."""
        if segment_type == "cta":
            return self.render_cta(
                price=script_text[:10],
                slogan=script_text[10:25] if len(script_text) > 10 else "",
                output_dir=output_dir,
                duration=duration,
                **kwargs,
            )
        return self.render_hook(
            keyword=script_text[:15],
            emotion=kwargs.pop("emotion", "震惊"),
            output_dir=output_dir,
            duration=duration,
            **kwargs,
        )


# ── Remotion Engine (Node.js microservice) ──

class RemotionRenderer(VideoRenderer):
    """Render overlays via the Remotion microservice (Node.js + Chromium).

    Produces high-fidelity spring/bounce animations with alpha channel.
    Requires the remotion-overlay-service to be running on :3001.
    """

    def __init__(self, service_url: str) -> None:
        self._url = service_url.rstrip("/")

    @property
    def name(self) -> str:
        return "Remotion (高级动效引擎)"

    def available(self) -> bool:
        try:
            import httpx
            resp = httpx.get(f"{self._url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def render_cta(
        self,
        price: str,
        slogan: str = "",
        original_price: str | None = None,
        primary_color: str = "#FFD700",
        output_dir: str | Path | None = None,
        duration: float = 3.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        return self._call_remotion("cta", {
            "price": price,
            "slogan": slogan,
            "originalPrice": original_price,
            "primaryColor": primary_color,
        }, output_dir, duration)

    def render_hook(
        self,
        keyword: str,
        emotion: str = "震惊",
        output_dir: str | Path | None = None,
        duration: float = 2.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        return self._call_remotion("hook", {
            "keyword": keyword,
            "emotion": emotion,
        }, output_dir, duration)

    def _call_remotion(
        self,
        composition: str,
        props: dict[str, Any],
        output_dir: str | Path | None,
        duration: float,
    ) -> tuple[str | None, str | None]:
        try:
            import httpx
            resp = httpx.post(
                f"{self._url}/render",
                json={"composition": composition, "props": props, "width": 1080, "height": 1920, "fps": 30},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("videoUrl", "")
                if url:
                    dl = httpx.get(url, timeout=15)
                    out_dir = Path(output_dir or ".")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"remotion_{composition}_{hash(props.get('price', props.get('keyword', ''))):04x}.webm"
                    out_path.write_bytes(dl.content)
                    return str(out_path), None
            elif resp.status_code == 202:
                return None, "Remotion 渲染队列繁忙，已切换备用引擎"
            else:
                return None, f"Remotion 服务异常 (HTTP {resp.status_code})，已切换备用引擎"
        except Exception as exc:
            return None, f"Remotion 不可用 ({exc})，已切换备用引擎"


# ── Pillow Engine (always available) ──

class PillowRenderer(VideoRenderer):
    """Render overlays using Pillow + FFmpeg — pure Python, zero external services.

    Generates animated WebM clips with alpha channel via frame-by-frame
    Pillow rendering and FFmpeg VP9 encoding. Always available.
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    @property
    def name(self) -> str:
        return "Pillow (内置动画引擎)"

    def available(self) -> bool:
        return True  # Pillow is always available

    def render_cta(
        self,
        price: str,
        slogan: str = "",
        original_price: str | None = None,
        primary_color: str = "#FFD700",
        output_dir: str | Path | None = None,
        duration: float = 3.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        from services.animated_overlay import create_animated_overlay
        display_text = f"{price} {slogan}".strip()[:25]
        path = create_animated_overlay(
            text=display_text,
            output_dir=output_dir,
            duration=min(duration, 3.0),
            animation="pop_in",
            font_size=72,
            glow_color=(255, 215, 0),
            ffmpeg_path=self.ffmpeg_path,
        )
        return path, None

    def render_hook(
        self,
        keyword: str,
        emotion: str = "震惊",
        output_dir: str | Path | None = None,
        duration: float = 2.0,
        **kwargs: Any,
    ) -> tuple[str | None, str | None]:
        from services.animated_overlay import create_animated_overlay
        path = create_animated_overlay(
            text=keyword[:25],
            output_dir=output_dir,
            duration=min(duration, 2.5),
            animation="fade_in_up",
            font_size=56,
            glow_color=None,
            ffmpeg_path=self.ffmpeg_path,
        )
        return path, None


# ── Factory ──

class RendererFactory:
    """Create the best available renderer based on configuration and environment."""

    @staticmethod
    def create(
        remotion_url: str | None = None,
        ffmpeg_path: str = "ffmpeg",
        *,
        engine: str = "auto",
    ) -> VideoRenderer:
        """Factory method.

        Args:
            remotion_url: Remotion microservice URL (e.g. http://localhost:3001).
            ffmpeg_path: Path to FFmpeg binary.
            engine: "auto" (default), "remotion", or "pillow".

        Returns:
            A VideoRenderer instance ready to use.
        """
        if engine == "pillow":
            log.info("Renderer: Pillow (forced)")
            return PillowRenderer(ffmpeg_path=ffmpeg_path)

        if engine == "remotion":
            if not remotion_url:
                log.warning("Renderer: Remotion requested but no URL configured — falling back to Pillow")
                return PillowRenderer(ffmpeg_path=ffmpeg_path)
            r = RemotionRenderer(remotion_url)
            if r.available():
                log.info("Renderer: Remotion (forced)")
                return r
            log.warning("Renderer: Remotion requested but unavailable — falling back to Pillow")
            return PillowRenderer(ffmpeg_path=ffmpeg_path)

        # "auto": try Remotion first, fall back to Pillow
        if remotion_url:
            r = RemotionRenderer(remotion_url)
            if r.available():
                log.info("Renderer: Remotion (auto-detected)")
                return r
            log.info("Renderer: Remotion unavailable, using Pillow")

        log.info("Renderer: Pillow (auto)")
        return PillowRenderer(ffmpeg_path=ffmpeg_path)
