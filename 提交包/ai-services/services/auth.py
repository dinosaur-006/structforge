"""Simple API key authentication middleware for demo/prototype deployment."""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests missing or having an incorrect API key.

    Does NOT protect /health or / (root) endpoints.
    """

    def __init__(self, app, api_key: str | None = None) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health, root, and static file paths.
        if self._skip_auth(request.url.path):
            return await call_next(request)

        # If no API key is configured, allow all requests.
        if not self.api_key:
            return await call_next(request)

        # Check the X-API-Key header.
        provided = request.headers.get("X-API-Key", "")
        if provided == self.api_key:
            return await call_next(request)

        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    def _skip_auth(self, path: str) -> bool:
        return path in ("/", "/health") or path.startswith("/outputs/")
