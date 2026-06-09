"""StructForge Prompt Engine — multi-layer, multi-platform text-to-video prompt generation.

Layers:
    1. SUBJECT  — who/what is in frame
    2. ACTION   — what is happening
    3. CAMERA   — shot size + movement
    4. STYLE    — lighting + color + texture
    5. CONSTRAINTS — negative prompts + technical params

Platforms:
    - seedance (Doubao Seedance 2.0)
    - runway   (Runway Gen-3/Gen-4)
    - kling    (Kuaishou Kling)
"""

from .engine import AIVideoPromptEngine
from .assembler import PromptAssembler, PromptResult
from .vocabulary import PRODUCT_VOCABULARY, EMOTION_CAMERA_MAP

__all__ = [
    "AIVideoPromptEngine",
    "PromptAssembler",
    "PromptResult",
    "PRODUCT_VOCABULARY",
    "EMOTION_CAMERA_MAP",
]
