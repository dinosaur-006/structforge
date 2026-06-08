export interface CtaProps {
  price: string;
  originalPrice?: string;
  slogan: string;
  primaryColor: string;
}

export interface HookProps {
  keyword: string;
  emotion: '震惊' | '好奇' | '恐惧' | '共鸣';
}

export type CompositionName = 'cta' | 'hook';

export interface RenderRequest {
  composition: CompositionName;
  props: CtaProps | HookProps;
  width?: number;
  height?: number;
  fps?: number;
  durationSeconds?: number;
}

export interface RenderResponse {
  videoUrl: string;
  durationMs: number;
  renderTimeMs: number;
}
