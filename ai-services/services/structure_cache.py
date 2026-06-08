"""Disk-based structure analysis cache keyed by video content fingerprint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from models.schemas import VideoStructure


class StructureCache:
    """Caches analysis results so repeated runs for the same video are instant."""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = Path(cache_dir or "data/structure-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fingerprint(
        self,
        *,
        duration: float,
        resolution: str,
        scene_count: int,
        audio_segment_count: int,
        file_size: int = 0,
        content_sample: bytes = b"",
    ) -> str:
        """Compute a stable fingerprint from video metadata + partial content hash.

        Includes first+last 4KB of file content to prevent different videos
        with similar duration/size from colliding in the cache.
        """
        content_hash = hashlib.sha256(content_sample).hexdigest()[:12] if content_sample else "0"*12
        raw = f"{duration:.2f}|{resolution}|{scene_count}|{audio_segment_count}|{file_size}|{content_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, fingerprint: str) -> VideoStructure | None:
        """Return cached structure or None."""
        cache_file = self.cache_dir / f"{fingerprint}.json"
        if not cache_file.exists():
            return None
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            return VideoStructure.model_validate(payload)
        except Exception:
            return None

    def put(self, fingerprint: str, structure: VideoStructure) -> None:
        """Cache a structure."""
        cache_file = self.cache_dir / f"{fingerprint}.json"
        payload = structure.model_dump(mode="json", by_alias=True)
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def invalidate(self, fingerprint: str) -> None:
        """Remove a cached entry."""
        cache_file = self.cache_dir / f"{fingerprint}.json"
        cache_file.unlink(missing_ok=True)
