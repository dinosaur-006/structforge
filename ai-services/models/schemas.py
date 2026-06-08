from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    productName: str = ""


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
    visual_keywords: list[str] = Field(default_factory=list)
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
    subtitleStyle: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    overlays: list[str] = Field(default_factory=list)

    @field_validator("subtitleStyle", mode="before")
    @classmethod
    def _coerce_subtitle_style(cls, v: object) -> list[str]:
        """Accept string from LLM, auto-wrap to list."""
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []

    @field_validator("overlays", mode="before")
    @classmethod
    def _coerce_overlays(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []


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


class AnalysisSampleOut(StrictModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    result: VideoStructure | None = None
    isReference: bool


CapabilityState = Literal["configured", "fallback", "disabled", "inline", "worker"]


class CapabilityItem(StrictModel):
    state: CapabilityState
    label: str
    detail: str


class CapabilityStatusOut(StrictModel):
    llm: CapabilityItem
    vision: CapabilityItem
    asr: CapabilityItem
    aigc: CapabilityItem
    videoGeneration: CapabilityItem | None = None
    taskExecution: CapabilityItem


ProjectStatus = Literal["draft", "analyzing", "editing", "rendering", "completed"]


class ProjectBrief(StrictModel):
    productName: str = ""
    sellingPoints: list[str] = Field(default_factory=list)
    targetAudience: str = ""
    offer: str = ""
    tone: str = ""
    mandatoryClaims: list[str] = Field(default_factory=list)


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1)
    description: str = ""
    brief: ProjectBrief = Field(default_factory=ProjectBrief)


class ProjectUpdate(StrictModel):
    name: str | None = None
    description: str | None = None
    brief: ProjectBrief | None = None


class ProjectOut(StrictModel):
    id: str
    name: str
    description: str
    brief: ProjectBrief
    status: ProjectStatus
    updatedAt: str


class ReorderRequest(StrictModel):
    order: list[str] = Field(min_length=1)


class StructureActionResponse(StrictModel):
    action: Literal["undo", "redo"]
    available: bool
    structure: VideoStructure


class NLEditRequest(StrictModel):
    command: str


class NLEditResponse(StrictModel):
    structure: VideoStructure
    changes_summary: str


AssetType = Literal["image", "video", "text"]
MatchStatus = Literal["matched", "partial", "unmatched"]
AssetOrigin = Literal["uploaded", "packaging", "aigc", "recompose"]


class AssetRecommendation(StrictModel):
    segmentId: str
    label: str
    score: float = Field(ge=0, le=100)


class AssetOut(StrictModel):
    id: str
    name: str
    type: AssetType
    tag: str
    matchStatus: MatchStatus
    matchScore: float = Field(ge=0, le=100)
    color: str
    origin: AssetOrigin
    recommendedSegments: list[AssetRecommendation] = Field(default_factory=list)
    reason: str


class AssetAnalyzeResponse(StrictModel):
    asset_id: str
    analysis: dict[str, Any]


class AssetMatch(StrictModel):
    asset_id: str
    segment_id: str
    score: float = Field(ge=0, le=100)
    status: MatchStatus


class AssetMatchResponse(StrictModel):
    matches: list[AssetMatch]


GapSeverity = Literal["critical", "warning"]
GapStatus = Literal["open", "fixed"]
GapStrategyId = Literal["reorder", "packaging", "aigc", "recompose"]


class GapStrategy(StrictModel):
    id: GapStrategyId
    name: str
    description: str
    available: bool
    unavailableReason: str | None = None


class MaterialGapOut(StrictModel):
    id: str
    segmentId: str
    severity: GapSeverity
    description: str
    requiredSlot: str
    selectedStrategyId: GapStrategyId
    recommendedStrategy: GapStrategyId
    strategies: list[GapStrategy]
    status: GapStatus


class GapListResponse(StrictModel):
    gaps: list[MaterialGapOut]


class GapFixRequest(StrictModel):
    gap_id: str
    strategy: str


class GapFixResponse(StrictModel):
    gap_id: str
    status: GapStatus
    updated_structure: VideoStructure | None = None
    assets: list[AssetOut] = Field(default_factory=list)
    gaps: list[MaterialGapOut] = Field(default_factory=list)


class GapFixAllResponse(StrictModel):
    fixed_count: int = Field(ge=0)
    details: list[GapFixResponse]
    gaps: list[MaterialGapOut]
    updated_structure: VideoStructure | None = None
    assets: list[AssetOut] = Field(default_factory=list)


FinalScriptStyle = Literal["high_click", "high_conversion", "fast_pace", "high_quality", "xiaohongshu_ces", "wechat_social", "default"]
FinalSegmentSource = Literal["original", "reorder", "packaging", "aigc", "recompose"]


class FinalSegment(StrictModel):
    id: str
    type: SegmentType
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(ge=0)
    script: str                    # Clean spoken script (NO production params)
    visual: str                    # Visual description for the scene
    asset_id: str | None = None
    subtitle_style: str
    transition: str
    locked: bool = False
    source: FinalSegmentSource = "original"
    source_start: float | None = Field(default=None, ge=0)
    source_end: float | None = Field(default=None, ge=0)
    # ── Production parameters (separate from script text) ──
    camera: str = "静态"           # 镜头运动: 静态/缓推/快推/拉远/横移/跟随/手持微晃
    subtitle_anim: str = "淡入"    # 字幕动画: 弹入/淡入/逐字出现/缩放出现/无动画
    pace: str = "正常"             # 语速: 快/正常/慢
    emotion: str = "亲切"          # 语气: 惊讶/紧迫/亲切/权威/感动/兴奋/平静
    visual_fx: str = "无"          # 画面特效: 无/震屏/闪白/慢动作/放大/模糊过渡
    # ── Structured visual requirements for gap auditing ──
    visual_requirements: dict[str, str] = Field(default_factory=dict)
    # e.g. {{"scene": "满是油污的厨房", "action": "皱眉抓狂", "object": "手持清洁剂特写", "emotion": "紧迫焦虑"}}


class FinalScript(StrictModel):
    version: FinalScriptStyle
    total_duration: float = Field(ge=0)
    segments: list[FinalSegment] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResultEvaluation(StrictModel):
    health: HealthScores
    material_coverage: float = Field(ge=0, le=100)
    product_first_exposure: float | None = None
    gap_count: int = Field(ge=0)
    cta_duration: float = Field(ge=0)


class ResultMetricComparison(StrictModel):
    before: str
    after: str
    delta: str
    positive: bool


class ResultMetrics(StrictModel):
    scoreDelta: int
    materialCoverage: ResultMetricComparison
    productExposure: ResultMetricComparison
    gapCount: ResultMetricComparison
    ctaDuration: ResultMetricComparison


class ResultTimelineOut(StrictModel):
    id: str
    label: str
    start: float
    end: float
    source: FinalSegmentSource
    thumbnail_url: str | None = None
    subtitle: str | None = None
    script: str | None = None


class ResultVersionOut(StrictModel):
    id: str
    name: str
    score: int
    metrics: ResultMetrics
    health: HealthScores
    timeline: list[ResultTimelineOut]


class ResultVersionsResponse(StrictModel):
    evaluationLabel: str
    baseline: ResultVersionOut
    versions: list[ResultVersionOut]


class MigrateRequest(StrictModel):
    style: FinalScriptStyle = "default"


class MigrateVariantRequest(StrictModel):
    style: Literal["high_click", "high_conversion", "fast_pace", "high_quality"]


RenderVersion = Literal["original", "safe_fix", "strong_hook", "strong_conversion"]
RenderStatus = Literal["pending", "processing", "completed", "failed"]
RenderResolution = Literal["720p", "1080p"]


class RenderRequest(StrictModel):
    version: RenderVersion
    resolution: RenderResolution = "1080p"
    script_version: FinalScriptStyle | None = None


class RenderJobResponse(StrictModel):
    job_id: str


class RenderProgress(StrictModel):
    status: RenderStatus
    progress: float = Field(ge=0, le=100)
    output_url: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
