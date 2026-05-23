export type ProjectStatus = 'draft' | 'analyzing' | 'editing' | 'rendering' | 'completed';
export type SegmentType = 'hook' | 'pain' | 'product' | 'proof' | 'cta';
export type AssetType = 'image' | 'video' | 'text';
export type MatchStatus = 'matched' | 'partial' | 'unmatched';
export type HealthTone = 'success' | 'warning' | 'error';
export type GapSeverity = 'critical' | 'warning';
export type GapStatus = 'open' | 'fixed';
export type SourceType = 'original' | 'reorder' | 'aigc' | 'packaging';
export type FinalScriptStyle = 'high_click' | 'high_conversion' | 'fast_pace' | 'high_quality' | 'default';

export interface Project {
  id: string;
  name: string;
  description: string;
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

export interface Asset {
  id: string;
  name: string;
  type: AssetType;
  tag: string;
  matchStatus: MatchStatus;
  matchScore: number;
  color: string;
}

export interface GapStrategy {
  id: string;
  name: string;
  description: string;
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
    hookAdvance: string;
    exposureAdvance: string;
    wasteReduction: string;
    ctaDuration: string;
  };
  health: HealthScores;
  timeline: ResultTimelineSegment[];
}

export interface ToastMessage {
  id: string;
  tone: 'success' | 'error' | 'info';
  title: string;
  description?: string;
}
