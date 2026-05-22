from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from config import Settings


class UploadValidationError(ValueError):
    pass


def validate_upload_metadata(
    *,
    content_type: str | None,
    filename: str | None,
    size_bytes: int,
    settings: Settings,
) -> None:
    if not content_type or not content_type.startswith("video/"):
        raise UploadValidationError("Only video files are supported")
    if size_bytes > settings.max_upload_bytes:
        raise UploadValidationError("File size exceeds 500MB")
    if not filename:
        raise UploadValidationError("A filename is required")


def new_job_id() -> str:
    return str(uuid4())


def save_upload_bytes(content: bytes, *, job_id: str, settings: Settings) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.upload_dir / f"{job_id}_source.mp4"
    output_path.write_bytes(content)
    return output_path
