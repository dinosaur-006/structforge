"""Async Remotion microservice client for animated overlays.

Falls back to Phase 7 Pillow animations when the service is unavailable.

NOTE (2026-06-10): This module is currently unused. RendererFactory in
renderer_abstraction.py handles Remotion calls via a different path.
Keep for future direct Remotion integration or delete if RendererFactory
fully replaces this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class RemotionClient:
    """HTTP client for the Remotion overlay rendering microservice."""

    def __init__(self, service_url: str | None = None) -> None:
        self._url = (service_url or "").rstrip("/")
        self._available = bool(self._url)

    @property
    def available(self) -> bool:
        return self._available

    async def render_cta(
        self,
        price: str,
        slogan: str = "",
        original_price: str | None = None,
        primary_color: str = "#FFD700",
    ) -> str | None:
        """Render a CTA spring animation overlay. Returns URL or None."""
        return await self._render("cta", {
            "price": price,
            "slogan": slogan,
            "originalPrice": original_price,
            "primaryColor": primary_color,
        })

    async def render_hook(self, keyword: str, emotion: str = "震惊") -> str | None:
        """Render a hook bounce animation overlay. Returns URL or None."""
        return await self._render("hook", {"keyword": keyword, "emotion": emotion})

    async def _render(self, composition: str, props: dict[str, Any]) -> str | None:
        """Call the Remotion service and return video URL."""
        if not self._available:
            return None
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._url}/render",
                    json={"composition": composition, "props": props, "width": 1080, "height": 1920, "fps": 30},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("videoUrl")
        except Exception:
            pass
        return None


# Synchronous fallback wrapper for use in non-async compositor
def render_remotion_overlay_sync(
    service_url: str | None,
    segment_type: str,
    script_text: str = "",
    font_size: int = 64,
    glow: tuple[int, int, int] | None = None,
    output_dir: str | Path | None = None,
    duration: float = 2.5,
    ffmpeg_path: str = "ffmpeg",
) -> tuple[str | None, str | None]:
    """Try Remotion first, fall back to Pillow. Returns (path, fallback_reason).

    fallback_reason is None when Remotion succeeded, or a human-readable
    Chinese reason when Pillow was used instead (e.g. queue full, unavailable).
    """
    # Try Remotion
    if service_url:
        try:
            import httpx
            props = {
                "price": script_text[:10],
                "slogan": script_text[10:25] if len(script_text) > 10 else "",
                "primaryColor": "#FFD700",
            } if segment_type == "cta" else {
                "keyword": script_text[:15],
                "emotion": "震惊",
            }
            resp = httpx.post(
                f"{service_url.rstrip('/')}/render",
                json={"composition": segment_type, "props": props, "width": 1080, "height": 1920, "fps": 30},
                timeout=25,
            )
            if resp.status_code == 200:
                url = resp.json().get("videoUrl", "")
                if url:
                    dl = httpx.get(url, timeout=15)
                    out_dir = Path(output_dir or ".")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"remotion_{segment_type}.webm"
                    out_path.write_bytes(dl.content)
                    return str(out_path), None  # success, no fallback reason
            elif resp.status_code == 202:
                return None, "Remotion 渲染队列繁忙，已使用备用动画引擎"
            else:
                return None, f"Remotion 服务异常 (HTTP {resp.status_code})，已使用备用动画引擎"
        except Exception:
            return None, "Remotion 服务不可用，已使用备用动画引擎"

    # Fallback: Phase 7 Pillow animation
    from services.animated_overlay import create_animated_overlay
    anim = "pop_in" if segment_type == "cta" else "fade_in_up"
    path = create_animated_overlay(
        text=script_text[:25],
        output_dir=output_dir,
        duration=duration,
        animation=anim,
        font_size=font_size,
        glow_color=glow,
        ffmpeg_path=ffmpeg_path,
    )
    reason = "Remotion 未配置，使用 Pillow 动画引擎" if not service_url else None
    return path, None if path else "动画生成失败"
