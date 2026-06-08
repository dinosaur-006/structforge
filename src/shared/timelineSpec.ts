/** TimelineSpec — structured video timeline protocol for AI-generated video previews.

 * LLM outputs this JSON alongside FinalScript. The frontend renders it
 * as an animated storyboard preview without needing the full FFmpeg pipeline.
 */

export interface TimelineSpec {
  composition: {
    fps: number;
    width: number;
    height: number;
    totalFrames: number;
    durationSeconds: number;
  };
  tracks: TimelineTrack[];
}

export interface TimelineTrack {
  id: string;
  type: 'video' | 'subtitle' | 'audio';
  label: string;
  clips: TimelineClip[];
}

export interface TimelineClip {
  id: string;
  startFrame: number;
  durationInFrames: number;
  /** Component name from ComponentRegistry */
  component: 'TitleCard' | 'SplitScreen' | 'StatCard' | 'QuoteCard' | 'ProductHero' | 'CTACard' | 'OverlayText';
  props: Record<string, unknown>;
}

// ── Component Registry — LLM can only use these ──
export const COMPONENT_REGISTRY = {
  TitleCard: {
    description: '全屏标题卡 — 用于Hook段制造第一帧冲击',
    props: ['title', 'subtitle', 'backgroundColor', 'textColor', 'animation'],
  },
  SplitScreen: {
    description: '前后对比分屏 — 用于Proof段的Before/After展示',
    props: ['leftLabel', 'rightLabel', 'leftImage', 'rightImage', 'dividerLabel'],
  },
  StatCard: {
    description: '数据展示卡 — 用于Proof段的权威数据背书',
    props: ['statValue', 'statLabel', 'source', 'badge', 'backgroundColor'],
  },
  QuoteCard: {
    description: '评价/引述卡 — 用于社交裂变和信任背书',
    props: ['quote', 'author', 'avatar', 'rating', 'backgroundColor'],
  },
  ProductHero: {
    description: '产品英雄镜头 — 用于Product段的视觉展示',
    props: ['productName', 'imageUrl', 'tagline', 'animation'],
  },
  CTACard: {
    description: '转化行动卡 — 用于CTA段的紧迫感引导',
    props: ['title', 'price', 'originalPrice', 'deadline', 'buttonText', 'urgencyLevel'],
  },
  OverlayText: {
    description: '叠加字幕 — 用于分镜的字幕展示',
    props: ['text', 'fontSize', 'position', 'animation', 'color'],
  },
} as const;

export type ComponentName = keyof typeof COMPONENT_REGISTRY;

// ── LLM output wrapper ──
export interface TimelineSpecResponse {
  timelineSpec: TimelineSpec | null;
  componentsUsed: string[];
  previewDuration: number;
}
