"""AI video generation via Doubao Seedance API.

Uses Seedance 2.0 for text-to-video or image-to-video generation.
Two-step async API: create task → poll until complete → download video.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

CREATE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
QUERY_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}"


class VideoGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "doubao-seedance-2-0-260128",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._available = bool(api_key)

    @property
    def available(self) -> bool:
        return self._available

    def generate(
        self,
        prompt: str,
        output_path: Path,
        *,
        duration: int = 5,
        ratio: str = "9:16",
        resolution: str = "720p",
    ) -> bool:
        """Generate a video from text prompt. Returns True on success.

        Retries up to 2 times on transient failures (5xx, network errors).

        Set MOCK_AI_GEN=true in environment to generate a synthetic test clip
        (colored gradient + text overlay) instead of calling the real API.
        Imported lazily from os.environ on first call.
        """
        import os

        # ── Mock mode: generate synthetic test clip ──
        if os.getenv("MOCK_AI_GEN", "").lower() == "true":
            return self._generate_mock(prompt, output_path, duration)

        if not self._available or not prompt.strip():
            return False

        last_error: str | None = None
        for attempt in range(3):  # 1 initial + 2 retries
            try:
                # Step 1: Create task
                resp = httpx.post(
                    CREATE_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "content": [{"type": "text", "text": prompt.strip()}],
                        "duration": max(4, min(duration, 12)),
                        "ratio": ratio,
                        "resolution": resolution,
                        "watermark": False,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                task_id = resp.json().get("id", "")
                if not task_id:
                    last_error = "No task ID in response"
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    return False

                # Step 2: Poll until complete (max 120s)
                for _ in range(40):
                    time.sleep(3)
                    qr = httpx.get(
                        QUERY_URL.format(task_id=task_id),
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=15,
                    )
                    qr.raise_for_status()
                    payload = qr.json()
                    status = payload.get("status", "")
                    if status == "succeeded":
                        video_url = payload.get("content", {}).get("video_url", "") or payload.get("video_url", "")
                        if video_url:
                            vr = httpx.get(video_url, timeout=60)
                            vr.raise_for_status()
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            output_path.write_bytes(vr.content)
                            return True
                        return False
                    if status in ("failed", "expired"):
                        return False

                # Poll exhausted
                last_error = "Task timed out after 120s"
                return False

            except httpx.HTTPStatusError as exc:
                # Retry on server errors (5xx), fail on client errors (4xx)
                if 500 <= exc.response.status_code < 600 and attempt < 2:
                    last_error = f"HTTP {exc.response.status_code}"
                    time.sleep(2 ** attempt)
                    continue
                return False
            except Exception as exc:
                if attempt < 2:
                    last_error = str(exc)
                    time.sleep(2 ** attempt)
                    continue
                return False

        return False

    def _generate_mock(self, prompt: str, output_path: Path, duration: int) -> bool:
        """Generate a synthetic test video using FFmpeg (no API call).

        Creates a colored gradient background with the prompt text overlaid.
        Used when MOCK_AI_GEN=true for demo/testing without real API access.
        """
        import subprocess
        # Pick a random-ish color based on prompt hash
        hue = (hash(prompt) % 360 + 360) % 360
        r1, g1, b1 = _hsl_to_rgb(hue / 360, 0.6, 0.3)
        r2, g2, b2 = _hsl_to_rgb(((hue + 40) % 360) / 360, 0.4, 0.15)

        # Truncate prompt for overlay text
        short_text = prompt.replace("竖屏短视频画面，9:16构图：", "").replace("，写实风格，高清", "")[:30]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x{r1:02x}{g1:02x}{b1:02x}:s=1080x1920:d={duration}:r=30",
            "-f", "lavfi",
            "-i", f"color=c=0x{r2:02x}{g2:02x}{b2:02x}:s=1080x1920:d={duration}:r=30",
            "-filter_complex",
            f"[0:v][1:v]blend=all_expr='A*(1-min(T/2,1))+B*min(T/2,1)'[bg];"
            f"[bg]drawtext=text='{short_text}':fontsize=52:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:borderw=3:bordercolor=black@0.5[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            return output_path.exists() and output_path.stat().st_size > 1000
        except Exception:
            return False

    def generate_from_image(
        self,
        prompt: str,
        image_path: Path,
        output_path: Path,
        *,
        duration: int = 5,
        ratio: str = "9:16",
        resolution: str = "720p",
    ) -> bool:
        """Generate video from image + text prompt."""
        if not self._available or not image_path.exists():
            return False

        import base64
        ext = image_path.suffix.lower().replace(".", "")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
        b64 = base64.b64encode(image_path.read_bytes()).decode()

        try:
            resp = httpx.post(
                CREATE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b64}"}},
                        {"type": "text", "text": prompt.strip()},
                    ],
                    "duration": max(4, min(duration, 12)),
                    "ratio": ratio,
                    "resolution": resolution,
                    "watermark": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            task_id = resp.json().get("id", "")
            if not task_id:
                return False

            for _ in range(40):
                time.sleep(3)
                qr = httpx.get(
                    QUERY_URL.format(task_id=task_id),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=15,
                )
                qr.raise_for_status()
                payload = qr.json()
                status = payload.get("status", "")
                if status == "succeeded":
                    video_url = payload.get("content", {}).get("video_url", "") or payload.get("video_url", "")
                    if video_url:
                        vr = httpx.get(video_url, timeout=60)
                        vr.raise_for_status()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(vr.content)
                        return True
                    return False
                if status in ("failed", "expired"):
                    return False
            return False
        except Exception:
            return False


# ── Master Commercial Prompt Engine ──

# Camera movement → cinematic English terminology
_CAMERA_ENG_MAP: dict[str, str] = {
    "快推": "Dynamic fast 3D camera zoom-in, action-packed focus shot",
    "缓推": "Cinematic high-end slow push-in tracking shot, smooth slide",
    "手持微晃": "Intense realistic handheld camera shake, chaotic aesthetic",
    "横移": "Elegant dolly tracking shot, horizontal sweeping view",
    "拉远": "Slow dramatic pull-back reveal, wide establishing shot",
    "跟随": "Smooth follow-cam tracking, steady gimbal movement",
    "静态": "Locked-off stable tripod shot, hyper-focused framing",
}

# Visual FX → post-processing instructions
_FX_ENG_MAP: dict[str, str] = {
    "慢动作": "High-speed photography, crisp 120fps slow motion playback",
    "震屏": "Screen shake visual effect, high energy impact, camera quake",
    "闪白": "Dramatic flash exposure lighting transition, high contrast bloom",
    "放大": "Dynamic scale-up zoom effect, cinematic crash zoom",
    "模糊过渡": "Cinematic lens blur transition, smooth defocus ramp",
    "无": "Clean photorealistic render, no post effects",
}


def build_master_prompt(segment_data: dict) -> str:
    """Assemble a high-end commercial prompt for Seedance / AIGC generation.

    Uses the director's visual_physics + camera + visual_fx fields to build
    a professional cinematography prompt that AI video models can execute reliably.

    Falls back gracefully when visual_physics is not available (old script format).
    """
    physics = segment_data.get("visual_physics", "")
    if not physics:
        # Backward compat: use visual description as physics
        physics = segment_data.get("visual", "A beautiful commercial product shot")

    camera = _CAMERA_ENG_MAP.get(segment_data.get("camera", "静态"), "Static locked-off shot")
    fx = _FX_ENG_MAP.get(segment_data.get("visual_fx", "无"), "Clean photorealistic render")

    return (
        f"Commercial advertisement style, 9:16 vertical aspect ratio, "
        f"shot on Arri Alexa 65. Hyper-realistic 8k resolution, "
        f"volumetric studio lighting, exquisite detail, masterpiece. "
        f"Subject and environment: {physics}. "
        f"Camera technique: {camera}. "
        f"Post-processing effect: {fx}. --ar 9:16 --style raw"
    )


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    """Convert HSL to RGB. All values in 0..1 range. Returns (r,g,b) 0..255."""
    if s == 0:
        val = int(l * 255)
        return val, val, val

    def hue2rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = hue2rgb(p, q, h + 1 / 3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1 / 3)
    return int(r * 255), int(g * 255), int(b * 255)
