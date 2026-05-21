import type { ProjectStatus, SourceType } from './types';

export const projectStatusMeta: Record<ProjectStatus, { label: string; tone: 'success' | 'warning' | 'error' | 'info' }> = {
  draft: { label: '\u8349\u7a3f', tone: 'info' },
  analyzing: { label: '\u5206\u6790\u4e2d', tone: 'warning' },
  editing: { label: '\u7f16\u8f91\u4e2d', tone: 'info' },
  rendering: { label: '\u6e32\u67d3\u4e2d', tone: 'warning' },
  completed: { label: '\u5df2\u5b8c\u6210', tone: 'success' },
};

export const sourceMeta: Record<SourceType, { label: string; color: string; borderClass: string }> = {
  original: { label: '\u539f\u7d20\u6750', color: '#4A8C6F', borderClass: 'border-l-success' },
  reorder: { label: '\u7ed3\u6784\u91cd\u6392', color: '#D4A24E', borderClass: 'border-l-warning' },
  aigc: { label: 'AIGC \u751f\u6210', color: '#C87D53', borderClass: 'border-l-accent' },
  packaging: { label: '\u5305\u88c5\u8865\u5168', color: '#5C8B67', borderClass: 'border-l-primary' },
};
