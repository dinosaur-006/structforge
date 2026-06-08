"""Pydantic data models for the video optimization pipeline v3.

All data structures are strictly typed to ensure seamless handoff between phases.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ── Phase 0: Product & Structure ──

class ProductType(str, Enum):
    BEAUTY = "beauty"
    ELECTRONICS = "electronics"
    FOOD = "food"
    CLOTHING = "clothing"
    OTHER = "other"


class SellingPointNature(str, Enum):
    APPEARANCE = "appearance"
    FUNCTION = "function"
    VALUE = "value"
    BRAND = "brand"


class PlatformType(str, Enum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"


class ProductProfile(StrictModel):
    """Complete product information for structure generation."""
    name: str
    product_type: ProductType = ProductType.OTHER
    selling_points: list[str] = Field(default_factory=list)
    target_audience: str = ""
    offer: str = ""
    tone: str = ""
    selling_point_nature: SellingPointNature = SellingPointNature.FUNCTION
    platform: PlatformType = PlatformType.DOUYIN


class SubtitleType(str, Enum):
    NONE = "none"            # < 30% of frames have text
    PARTIAL = "partial"      # 30-70% have text
    HARD_SUB = "hard_sub"    # > 70% have text, consistent style


class SegmentType(str, Enum):
    HOOK = "hook"
    PAIN = "pain"
    PRODUCT = "product"
    PROOF = "proof"
    CTA = "cta"
    COMPARE = "compare"
    DEMO = "demo"
    SCENE = "scene"
    OFFER = "offer"
    RESULT = "result"
    TUTORIAL = "tutorial"
    ATTRACT = "attract"
    VISUAL = "visual"
    LIFESTYLE = "lifestyle"
    PROBLEM = "problem"
    PRICE = "price"
    INGREDIENTS = "ingredients"
    HEALTH = "health"
    TASTE = "taste"


class StructureSegment(StrictModel):
    """One segment in the dynamically generated video structure."""
    id: str
    type: SegmentType
    label: str
    target_duration: float = Field(ge=0.5, le=15.0)
    narrative_description: str = ""
    screen_subtitle: str = ""       # Keywords for on-screen display
    tts_script: str = ""            # Full text for TTS voiceover


class DynamicStructure(StrictModel):
    """LLM-generated optimal video structure with constraint validation."""
    generation_method: str = "llm_dynamic"
    constraints_passed: bool = True
    total_duration: float = Field(ge=18.0, le=30.0)
    segments: list[StructureSegment] = Field(min_length=3, max_length=8)


# ── Phase 1: Shot Analysis ──

class ShotType(str, Enum):
    CLOSEUP = "closeup"
    MEDIUM = "medium"
    WIDE = "wide"
    OVERHEAD = "overhead"
    LOW_ANGLE = "low_angle"
    EYE_LEVEL = "eye_level"


class MotionType(str, Enum):
    STATIC = "static"
    SLOW_PUSH = "slow_push"
    FAST_PUSH = "fast_push"
    PULL_OUT = "pull_out"
    PAN = "pan"
    TRACKING = "tracking"
    HANDHELD = "handheld"
    ROTATION = "rotation"


class EmotionLabel(str, Enum):
    HIGH_ENERGY = "high_energy"
    TENSE = "tense"
    CALM = "calm"
    MOVING = "moving"
    EXCITED = "excited"
    URGENT = "urgent"
    WARM = "warm"


class AudioQuality(str, Enum):
    CLEAR = "clear"        # > 0.6
    NOISY = "noisy"        # 0.3 - 0.6
    DEGRADED = "degraded"  # < 0.3 — fall back to vision-only


class VisionAnalysis(StrictModel):
    """Per-shot visual analysis."""
    description: str = ""
    shot_type: ShotType = ShotType.EYE_LEVEL
    motion_type: MotionType = MotionType.STATIC
    emotion_label: EmotionLabel = EmotionLabel.CALM
    tags: list[str] = Field(default_factory=list)
    ocr_text: list[str] = Field(default_factory=list)
    dominant_colors: list[str] = Field(default_factory=list)
    has_product: bool = False
    product_colors: list[str] = Field(default_factory=list)


class AudioAnalysis(StrictModel):
    """Per-shot audio analysis with confidence scoring."""
    asr_text: str = ""
    asr_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sound_events: list[str] = Field(default_factory=list)
    sound_events_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    volume_curve: list[float] = Field(default_factory=list)
    quality_label: AudioQuality = AudioQuality.DEGRADED


class ShotContext(StrictModel):
    """Position and adjacency info."""
    position_in_video: float = 0.0  # normalized 0-1
    prev_scene_type: str = ""
    next_scene_type: str = ""
    duration_s: float = 0.0


class ShotQuality(StrictModel):
    """Visual quality metrics."""
    sharpness: float = Field(default=0.0, ge=0.0, le=1.0)
    brightness: float = Field(default=0.5, ge=0.0, le=1.0)
    composition_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ShotInfo(StrictModel):
    """Complete shot annotation from Phase 1."""
    id: str
    start_s: float
    end_s: float
    duration_s: float
    mid_frame_path: str = ""
    vision: VisionAnalysis = Field(default_factory=VisionAnalysis)
    audio: AudioAnalysis = Field(default_factory=AudioAnalysis)
    context: ShotContext = Field(default_factory=ShotContext)
    quality: ShotQuality = Field(default_factory=ShotQuality)


class ShotPool(StrictModel):
    """Collection of annotated shots from the original video."""
    source_video_id: str
    source_video_path: str
    shots: list[ShotInfo] = Field(default_factory=list)


# ── Phase 2: Subtitle ──

class SubtitleEvent(StrictModel):
    """A single subtitle overlay event."""
    segment_id: str
    start_s: float
    end_s: float
    text: str
    position: Literal["center_top", "bottom_center", "center"] = "bottom_center"
    font_size: int = 48
    effect: Literal["bounce_in", "fade_in", "char_by_char", "scale_in", "none"] = "none"
    bg_color: str = "semi-transparent black"


# ── Phase 3: Decision & Edit Plan ──

class RenderDecision(str, Enum):
    KEEP = "keep"             # Use original clip directly
    RE_EDIT = "re-edit"       # Cut/speed-change/rearrange from shot pool
    AI_GENERATE = "ai-generate"  # Generate new video via Seedance


class EditOperation(StrictModel):
    """FFmpeg operations for a single clip."""
    trim_start_s: float = 0.0
    trim_end_s: float = 0.0
    speed_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    mute_original: bool = True
    lut_preset: str | None = None
    protect_product_color: bool = False


class DecisionResult(StrictModel):
    """Decision + operation for one segment."""
    segment_id: str
    decision: RenderDecision
    matched_shot_id: str | None = None
    matched_score: float = 0.0
    operation: EditOperation = Field(default_factory=EditOperation)
    evidence: str = ""


class TransitionType(str, Enum):
    HARD_CUT = "hard_cut"
    DISSOLVE = "dissolve"
    SLIDE_LEFT = "slide_left"
    ZOOM_IN = "zoom_in"


class TransitionEvent(StrictModel):
    """Transition between two segments."""
    from_segment_id: str
    to_segment_id: str
    transition: TransitionType = TransitionType.HARD_CUT
    dissolve_duration_s: float = 0.0
    aligned_to_tts: bool = False
    aligned_to_bpm: bool = False
    cue_time_s: float = 0.0


class EditPlan(StrictModel):
    """Complete timeline plan for video assembly."""
    product: ProductProfile
    structure: DynamicStructure
    shot_pool: ShotPool
    decisions: list[DecisionResult] = Field(default_factory=list)
    transitions: list[TransitionEvent] = Field(default_factory=list)
    subtitles: list[SubtitleEvent] = Field(default_factory=list)
    bgm_path: str = ""
    output_path: str = ""
    special_transition_count: int = Field(default=0, ge=0, le=2)
