from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if ffmpeg is None or ffprobe is None:
    pytest.skip("ffmpeg/ffprobe not installed; media integration test skipped", allow_module_level=True)

from config import Settings
from models.repository import SQLiteRepository
from services.pipeline import AnalysisPipeline


def test_pipeline_generates_frontend_structure_from_short_video(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=320x568:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=3",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
        str(video_path),
    ],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

    settings = Settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        db_path=tmp_path / "structforge.db",
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
    )
    repository = SQLiteRepository(settings.db_path)
    repository.initialize()
    repository.create_job("job-1", str(video_path))

    structure = AnalysisPipeline(settings=settings, repository=repository).run("job-1", video_path)

    assert len(structure.script) >= 3
    assert len(structure.rhythm) >= 5
    assert set(structure.model_dump(mode="json")) == {"meta", "script", "rhythm", "packaging", "health"}
