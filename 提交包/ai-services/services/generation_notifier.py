"""AIGC generation progress notifier via WebSocket.

Pushes real-time status updates to the frontend during async AI generation
(Seedance / Seedream), so users see "生成中..." progress instead of a blank wait.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger(__name__)


class GenerationNotifier:
    """Manages WebSocket connections for AIGC generation status updates.

    Each generation slot gets its own WebSocket channel. The frontend
    subscribes via ws://host/ws/generation/{slot_id} and receives
    JSON status messages until the generation completes or fails.
    """

    def __init__(self) -> None:
        from fastapi import WebSocket
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, slot_id: str, websocket: Any) -> None:
        """Register a WebSocket connection for a generation slot."""
        await websocket.accept()
        async with self._lock:
            self._connections[slot_id] = websocket
        log.info("GenerationNotifier: client connected for slot %s", slot_id)

    async def disconnect(self, slot_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.pop(slot_id, None)
        log.info("GenerationNotifier: client disconnected for slot %s", slot_id)

    async def notify(self, slot_id: str, status: str, **extra: Any) -> None:
        """Send a status update to the frontend for a specific slot.

        Args:
            slot_id: The generation slot identifier (e.g. segment ID).
            status: One of "queued", "generating", "completed", "failed".
            **extra: Additional fields to include in the JSON payload.
        """
        async with self._lock:
            ws = self._connections.get(slot_id)
        if ws is None:
            return
        try:
            await ws.send_json({"slot_id": slot_id, "status": status, **extra})
        except Exception:
            await self.disconnect(slot_id)

    async def notify_progress(self, slot_id: str, progress: float, message: str = "") -> None:
        """Send a progress update (0.0–1.0)."""
        await self.notify(slot_id, "generating", progress=round(progress, 2), message=message)

    async def notify_completed(self, slot_id: str, asset_url: str) -> None:
        """Notify that generation is complete with the result URL."""
        await self.notify(slot_id, "completed", asset_url=asset_url)

    async def notify_failed(self, slot_id: str, error: str) -> None:
        """Notify that generation failed."""
        await self.notify(slot_id, "failed", error=error)

    @property
    def active_slots(self) -> list[str]:
        """Return list of currently tracked slot IDs."""
        return list(self._connections.keys())


# ── Singleton ──

_notifier: GenerationNotifier | None = None


def get_notifier() -> GenerationNotifier:
    """Get or create the singleton GenerationNotifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = GenerationNotifier()
    return _notifier
