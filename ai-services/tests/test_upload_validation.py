from __future__ import annotations

import pytest

from config import Settings
from services.uploads import UploadValidationError, validate_upload_metadata


def test_upload_validation_rejects_non_video_mime() -> None:
    with pytest.raises(UploadValidationError, match="Only video files are supported"):
        validate_upload_metadata(
            content_type="text/plain",
            filename="notes.txt",
            size_bytes=128,
            settings=Settings(),
        )


def test_upload_validation_rejects_files_over_500mb() -> None:
    with pytest.raises(UploadValidationError, match="File size exceeds 500MB"):
        validate_upload_metadata(
            content_type="video/mp4",
            filename="large.mp4",
            size_bytes=501 * 1024 * 1024,
            settings=Settings(),
        )
