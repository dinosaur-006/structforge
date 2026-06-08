export type ProjectStatus = 'draft' | 'analyzing' | 'editing' | 'rendering' | 'completed';
export type SegmentType = 'hook' | 'pain' | 'product' | 'proof' | 'cta';
export type AssetType = 'image' | 'video' | 'text';
export type MatchStatus = 'matched' | 'partial' | 'unmatched';
export type AssetOrigin = 'uploaded' | 'packaging' | 'aigc' | 'recompose';
export type HealthTone = 'success' | 'warning' | 'error';
export type GapSeverity = 'critical' | 'warning';
export type GapStatus = 'open' | 'fixed';
export type SourceType = 'original' | 'reorder' | 'aigc' | 'packaging' | 'recompose';
export type FinalScriptStyle = 'high_click' | 'high_conversion' | 'fast_pace' | 'high_quality' | 'default';
export type RenderVersion = 'original' | 'safe_fix' | 'strong_hook' | 'strong_conversion';
export type RenderStatus = 'idle' | 'pending' | 'processing' | 'completed' | 'failed';
export type RenderResolution = '720p' | '1080p';
export type CapabilityState = 'configured' | 'fallback' | 'disabled' | 'inline' | 'worker';

export interface ProjectBrief {
  productName: string;
  sellingPoints: string[];
  targetAudience: string;
  offer: string;
  tone: string;
  mandatoryClaims: string[];
}

export interface Project {
  id: string;
  name: string;
  description: string;
  brief?: ProjectBrief;
  status: ProjectStatus;
  updatedAt: string;
  thumbnail?: string;
}

export interface VideoMeta {
  duration: number;
  resolution: string;
  shots: number;
  coverLabel: string;
}

export interface ScriptSegment {
  id: string;
  type: SegmentType;
  label: string;
  start: number;
  end: number;
  duration: number;
  goal: string;
  copy: string;
  visual: string;
  healthScore: number;
  locked?: boolean;
  assetId?: string;
  subtitlePreset?: string;
  transition?: string;
  beatAligned?: boolean;
}

export interface RhythmPoint {
  second: number;
  cuts: number;
  emotion: number;
  highlight?: boolean;
}

export interface PackagingStructure {
  subtitleStyle: string[];
  transitions: string[];
  overlays: string[];
}

export interface HealthScores {
  hook_strength: number;
  product_exposure_timing: number;
  selling_point_proof: number;
  pacing_compactness: number;
  cta_persuasiveness: number;
  overall: number;
}

export interface VideoStructure {
  meta: VideoMeta;
  script: ScriptSegment[];
  rhythm: RhythmPoint[];
  packaging: PackagingStructure;
  health: HealthScores;
}

export interface AnalysisSample {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  stage: string;
  result?: VideoStructure | null;
  isReference: boolean;
}

export interface CapabilityItem {
  state: CapabilityState;
  label: string;
  detail: string;
}

export interface Capabilities {
  llm: CapabilityItem;
  vision: CapabilityItem;
  asr: CapabilityItem;
  aigc: CapabilityItem;
  taskExecution: CapabilityItem;
}

export interface Asset {
  id: string;
  name: string;
  type: AssetType;
  tag: string;
  matchStatus: MatchStatus;
  matchScore: number;
  color: string;
  origin: AssetOrigin;
  recommendedSegments: Array<{ segmentId: string; label: string; score: number }>;
  reason: string;
}

export interface GapStrategy {
  id: string;
  name: string;
  description: string;
  available: boolean;
  unavailableReason?: string;
}

export interface MaterialGap {
  id: string;
  segmentId: string;
  severity: GapSeverity;
  description: string;
  requiredSlot: string;
  selectedStrategyId: string;
  recommendedStrategy: string;
  strategies: GapStrategy[];
  status: GapStatus;
}

export interface ResultTimelineSegment {
  id: string;
  label: string;
  start: number;
  end: number;
  source: SourceType;
  thumbnailUrl?: string | null;
  subtitle?: string | null;
  script?: string | null;
}

export interface WaveformData {
  data: number[];
  duration: number;
  labels: Array<{ start: number; end: number; type: string }>;
}

export interface FinalSegment {
  id: string;
  type: SegmentType;
  start: number;
  end: number;
  duration: number;
  script: string;
  visual: string;
  asset_id: string | null;
  subtitle_style: string;
  transition: string;
  locked: boolean;
  source: SourceType;
  source_start?: number | null;
  source_end?: number | null;
}

export interface FinalScript {
  version: FinalScriptStyle;
  total_duration: number;
  segments: FinalSegment[];
  metadata: {
    warnings?: string[];
    generated_at?: string;
    [key: string]: unknown;
  };
}

export interface ResultVersion {
  id: string;
  name: string;
  score: number;
  metrics: {
    scoreDelta: number;
    materialCoverage: MetricComparison;
    productExposure: MetricComparison;
    gapCount: MetricComparison;
    ctaDuration: MetricComparison;
  };
  health: HealthScores;
  timeline: ResultTimelineSegment[];
}

export interface MetricComparison {
  before: string;
  after: string;
  delta: string;
  positive: boolean;
}

export interface ResultVersionsResponse {
  evaluationLabel: string;
  baseline: ResultVersion;
  versions: ResultVersion[];
}

export interface ToastMessage {
  id: string;
  tone: 'success' | 'error' | 'info';
  title: string;
  description?: string;
}
