import type { ResultTimelineSegment, ResultVersion } from '../shared/types';

const baseTimeline: ResultTimelineSegment[] = [
  { id: 'r-hook', label: 'Hook', start: 0, end: 3, source: 'original' },
  { id: 'r-pain', label: '\u75db\u70b9', start: 3, end: 8, source: 'reorder' },
  { id: 'r-product', label: '\u4ea7\u54c1', start: 8, end: 12, source: 'original' },
  { id: 'r-proof-a', label: '\u5356\u70b9 A', start: 12, end: 20, source: 'aigc' },
  { id: 'r-proof-b', label: '\u5356\u70b9 B', start: 20, end: 26, source: 'original' },
  { id: 'r-cta', label: 'CTA', start: 26, end: 35, source: 'packaging' },
];

export const mockVersions: ResultVersion[] = [
  {
    id: 'original',
    name: '\u539f\u7248',
    score: 52,
    metrics: { scoreDelta: 0, materialCoverage: { before: '100%', after: '100%', delta: '0%', positive: true }, productExposure: { before: '8.0s', after: '8.0s', delta: '0.0s', positive: true }, gapCount: { before: '0', after: '0', delta: '0', positive: true }, ctaDuration: { before: '11.0s', after: '11.0s', delta: '0.0s', positive: true } },
    health: { hook_strength: 42, product_exposure_timing: 48, selling_point_proof: 46, pacing_compactness: 55, cta_persuasiveness: 39, overall: 52 },
    timeline: baseTimeline.map((segment) => ({ ...segment, source: 'original' })),
  },
  {
    id: 'safe-fix',
    name: '\u4fdd\u5b88\u4fee\u590d',
    score: 68,
    metrics: { scoreDelta: 16, materialCoverage: { before: '65%', after: '82%', delta: '+17%', positive: true }, productExposure: { before: '8.0s', after: '6.0s', delta: '-2.0s', positive: true }, gapCount: { before: '2', after: '1', delta: '-1', positive: true }, ctaDuration: { before: '3.0s', after: '4.2s', delta: '+1.2s', positive: true } },
    health: { hook_strength: 68, product_exposure_timing: 64, selling_point_proof: 61, pacing_compactness: 70, cta_persuasiveness: 58, overall: 68 },
    timeline: baseTimeline,
  },
  {
    id: 'strong-hook',
    name: 'Strong Hook',
    score: 81,
    metrics: { scoreDelta: 29, materialCoverage: { before: '65%', after: '98%', delta: '+33%', positive: true }, productExposure: { before: '8.0s', after: '3.5s', delta: '-4.5s', positive: true }, gapCount: { before: '2', after: '0', delta: '-2', positive: true }, ctaDuration: { before: '3.0s', after: '5.0s', delta: '+2.0s', positive: true } },
    health: { hook_strength: 91, product_exposure_timing: 80, selling_point_proof: 74, pacing_compactness: 85, cta_persuasiveness: 75, overall: 81 },
    timeline: baseTimeline,
  },
  {
    id: 'strong-conversion',
    name: '\u5f3a\u8f6c\u5316',
    score: 79,
    metrics: { scoreDelta: 27, materialCoverage: { before: '65%', after: '98%', delta: '+33%', positive: true }, productExposure: { before: '8.0s', after: '4.1s', delta: '-3.9s', positive: true }, gapCount: { before: '2', after: '0', delta: '-2', positive: true }, ctaDuration: { before: '3.0s', after: '6.1s', delta: '+3.1s', positive: true } },
    health: { hook_strength: 82, product_exposure_timing: 76, selling_point_proof: 72, pacing_compactness: 78, cta_persuasiveness: 88, overall: 79 },
    timeline: baseTimeline.map((segment) => (segment.id === 'r-cta' ? { ...segment, end: 35, source: 'packaging' } : segment)),
  },
];
