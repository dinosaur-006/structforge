"""Generate cover images using Doubao Seedream image model via ARK API."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from config import Settings
from models.schemas import VideoStructure

ARK_IMAGE_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


def _load_font(size: int, configured_path: Path | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        configured_path,
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


class CoverGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(
        self,
        structure: VideoStructure,
        keyframe_paths: list[Path],
        product_name: str = "",
    ) -> Path:
        """Generate a cover image. Tries ARK Seedream first, falls back to Pillow."""
        cover_dir = self.settings.output_dir / "covers"
        cover_dir.mkdir(parents=True, exist_ok=True)

        # Try ARK Seedream image generation (uses dedicated image API key).
        if self.settings.doubao_image_api_key:
            aigc_path = self._try_seedream(cover_dir, structure, product_name)
            if aigc_path is not None:
                return aigc_path

        # Fallback: Pillow composition.
        return self._render_pillow_cover(cover_dir, structure, keyframe_paths, product_name)

    def _try_seedream(self, cover_dir: Path, structure: VideoStructure, product_name: str) -> Path | None:
        """Generate cover via Doubao Seedream ARK Images API."""
        hook = next((s for s in structure.script if s.type == "hook"), None)
        product = product_name or "新品推荐"
        hook_text = hook.copy_text if hook else "惊艳新品"

        prompt = (
            f"电商短视频封面：{product}，{hook_text}。"
            f"竖版9:16构图，产品居中展示，专业布光，高对比度，"
            f"留出顶部和底部文字空间，简洁高级，商业摄影质感。"
        )

        try:
            resp = httpx.post(
                ARK_IMAGE_URL,
                headers={"Authorization": f"Bearer {self.settings.doubao_image_api_key}"},
                json={
                    "model": self.settings.doubao_image_model,
                    "prompt": prompt,
                    "size": "2048x2048",
                    "response_format": "b64_json",
                    "watermark": False,
                },
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            images = payload.get("data", [])

            if images and "b64_json" in images[0]:
                output = cover_dir / f"seedream_cover_{hash(prompt) & 0xFFFF:04x}.png"
                output.write_bytes(base64.b64decode(images[0]["b64_json"]))
                return output

            if images and "url" in images[0]:
                img_resp = httpx.get(images[0]["url"], timeout=30)
                img_resp.raise_for_status()
                output = cover_dir / f"seedream_cover_{hash(prompt) & 0xFFFF:04x}.png"
                output.write_bytes(img_resp.content)
                return output

        except Exception:
            pass
        return None

    def _render_pillow_cover(
        self,
        cover_dir: Path,
        structure: VideoStructure,
        keyframe_paths: list[Path],
        product_name: str,
    ) -> Path:
        """Pillow-based fallback cover composition."""
        canvas = Image.new("RGB", (1080, 1920), "#1A1A18")
        draw = ImageDraw.Draw(canvas)

        if keyframe_paths:
            try:
                bg = Image.open(keyframe_paths[0]).convert("RGB")
                bg = bg.resize((1080, 1920), Image.LANCZOS)
                bg = bg.point(lambda p: p * 0.45)
                canvas.paste(bg, (0, 0))
            except Exception:
                pass

        draw.rectangle((0, 660, 1080, 1260), fill=(0, 0, 0, 128))
        draw.rectangle((80, 680, 96, 1240), fill="#5C8B67")

        hook = next((s for s in structure.script if s.type == "hook"), None)
        title = product_name or (hook.copy_text if hook else "新品推荐")
        font_title = _load_font(64, self.settings.packaging_font_path)
        draw.text((140, 760), title, fill="#F5F4F0", font=font_title)

        font_sub = _load_font(32, self.settings.packaging_font_path)
        draw.text((140, 870), "StructForge AI Cover", fill="#9E9A90", font=font_sub)

        health = structure.health.overall
        font_badge = _load_font(28, self.settings.packaging_font_path)
        draw.rounded_rectangle((140, 960, 340, 1010), radius=16, fill="#5C8B67")
        draw.text((156, 968), f"Structure Score {health}/100", fill="#FFFFFF", font=font_badge)

        draw.rectangle((0, 1860, 1080, 1920), fill=(0, 0, 0, 80))
        draw.text((140, 1876), "StructForge AI Video Structure Migration", fill="#9E9A90", font=_load_font(24, self.settings.packaging_font_path))

        output = cover_dir / f"cover_{hash(title) & 0xFFFF:04x}.png"
        canvas.save(output, format="PNG")
        return output
