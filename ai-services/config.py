from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SERVICE_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STRUCTFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    output_dir: Path = PROJECT_ROOT / "data" / "outputs"
    db_path: Path = PROJECT_ROOT / "data" / "structforge.db"

    max_upload_bytes: int = 500 * 1024 * 1024
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    packaging_font_path: Path | None = None
    scene_threshold: float = 27.0
    max_keyframes: int = 60

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    whisperx_model: str = "large-v3"
    volcano_asr_endpoint: str | None = None
    volcano_asr_api_key: str | None = None
    volcano_asr_resource_id: str = "volc.seedasr.auc"

    doubao_vision_endpoint: str | None = None
    doubao_vision_api_key: str | None = None
    doubao_llm_endpoint: str | None = None
    doubao_llm_api_key: str | None = None
    doubao_llm_model: str = "doubao-seed-2-0-lite"
    jimeng_image_endpoint: str | None = None
    jimeng_image_api_key: str | None = None
    doubao_image_model: str = "doubao-seedream-5-0-260128"
    doubao_image_api_key: str | None = None
    doubao_video_model: str = "doubao-seedance-1-5-pro-251215"
    remotion_service_url: str | None = None
    llm_max_attempts: int = Field(default=3, ge=1, le=10)
    seed_demo: bool = False
    content_safety_enabled: bool = False
    content_safety_blocked_terms: str = ""
    api_key: str | None = None
    bgm_library_dir: str | None = None
    bgm_volume: float = 0.25
    tts_endpoint: str | None = None
    tts_api_key: str | None = None
    tts_voice: str = "zh_female_qingxin"
    tts_speed: float = 1.0
    gap_match_threshold: float = 60.0  # Lower in .env for permissive matching


def get_settings() -> Settings:
    return Settings()
