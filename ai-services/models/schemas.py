from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoMeta(StrictModel):
    duration: float = Field(ge=0)
    resolution: str
    shots: int = Field(ge=0)
    coverLabel: str


SegmentType = Literal["hook", "pain", "product", "proof", "cta"]


class ScriptSegment(StrictModel):
    id: str
    type: SegmentType
    label: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(ge=0)
    goal: str
    copy_text: str = Field(alias="copy")
    visual: str
    healthScore: int = Field(ge=0, le=100)
    locked: bool | None = None
    assetId: str | None = None
    subtitlePreset: str | None = None
    transition: str | None = None
    beatAligned: bool | None = None


class RhythmPoint(StrictModel):
    second: float = Field(ge=0)
    cuts: int = Field(ge=0)
    emotion: float = Field(ge=0, le=1)
    highlight: bool | None = None


class PackagingStructure(StrictModel):
    subtitleStyle: list[str]
    transitions: list[str]
    overlays: list[str]


class HealthScores(StrictModel):
    hook_strength: int = Field(ge=0, le=100)
    product_exposure_timing: int = Field(ge=0, le=100)
    selling_point_proof: int = Field(ge=0, le=100)
    pacing_compactness: int = Field(ge=0, le=100)
    cta_persuasiveness: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)


class VideoStructure(StrictModel):
    meta: VideoMeta
    script: list[ScriptSegment] = Field(min_length=1)
    rhythm: list[RhythmPoint] = Field(min_length=1)
    packaging: PackagingStructure
    health: HealthScores


class TaskProgress(StrictModel):
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    result: VideoStructure | None = None
    error: str | None = None


class AnalyzeResponse(StrictModel):
    job_id: str
