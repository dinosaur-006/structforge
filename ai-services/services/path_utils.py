"""UTF-8 path compatibility — prevents FFmpeg crashes with Chinese/non-ASCII paths."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def safe_video_input(path: str | Path) -> Path:
    """Copy video to temp English-only dir if path contains non-ASCII chars."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Video not found: {src}")
    # If path is pure ASCII, no copy needed
    try:
        str(src).encode("ascii")
        return src
    except UnicodeEncodeError:
        pass
    # Copy to safe temp dir
    tmp_dir = Path(tempfile.gettempdir()) / "structforge_input"
    tmp_dir.mkdir(exist_ok=True)
    stem = src.stem.encode("ascii", "ignore").decode()[:30] or "video"
    safe_path = tmp_dir / f"{stem}{src.suffix}"
    shutil.copy2(src, safe_path)
    return safe_path


def safe_output_path(path: str | Path) -> Path:
    """Ensure output goes to a path FFmpeg can handle."""
    out = Path(path)
    try:
        str(out).encode("ascii")
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    except UnicodeEncodeError:
        tmp_dir = Path(tempfile.gettempdir()) / "structforge_output"
        tmp_dir.mkdir(exist_ok=True)
        stem = out.stem.encode("ascii", "ignore").decode()[:30] or "output"
        return tmp_dir / f"{stem}{out.suffix}"


def run_ffmpeg(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Safe FFmpeg execution with list args (no shell parsing)."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
