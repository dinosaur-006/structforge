"""StructForge Core — unified service layer.

All AI capabilities accessed through a single object, avoiding
duplicate client creation. Pattern borrowed from Pixelle-Video's
PixelleVideoCore.

Usage:
    core = StructForgeCore(settings)
    result = core.llm.complete_json(prompt, response_type=SomeModel)
    audio = core.tts.synthesize(text, output_path)
    card = core.ai_video.generate(segment)
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

from config import Settings
from services.llm_client import RobustLLMClient


class StructForgeCore:
    """Centralized service access for all StructForge AI capabilities."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: RobustLLMClient | None = None
        self._tts: Any = None
        self._ai_video: Any = None
        self._bgm: Any = None

    def _endpoint(self) -> str:
        return str(self.settings.doubao_llm_endpoint or "")

    def _api_key(self) -> str:
        return str(self.settings.doubao_llm_api_key or "")

    def _model(self) -> str:
        return str(self.settings.doubao_llm_model)

    @cached_property
    def llm(self) -> RobustLLMClient:
        return RobustLLMClient(self._endpoint(), self._api_key(), self._model())

    @cached_property
    def tts(self) -> Any:
        from services.tts_engine import TTSEngine
        return TTSEngine(
            endpoint=self.settings.tts_endpoint or None,
            api_key=self.settings.tts_api_key,
            voice=self.settings.tts_voice,
            speed=self.settings.tts_speed,
            inference_mode="local" if not self.settings.tts_api_key else "api",
        )

    @cached_property
    def ai_video(self) -> Any:
        from services.ai_video_service import AIVideoService
        return AIVideoService(self.settings)

    @cached_property
    def bgm(self) -> Any:
        from services.bgm_engine import BGMEngine
        return BGMEngine(
            bgm_dir=getattr(self.settings, 'bgm_library_dir', None),
            ffmpeg_path=self.settings.ffmpeg_path,
        )
