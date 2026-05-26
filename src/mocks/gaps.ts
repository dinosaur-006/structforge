import type { MaterialGap } from '../shared/types';

export const mockGaps: MaterialGap[] = [
  {
    id: 'gap-hook',
    segmentId: 'seg-hook',
    severity: 'critical',
    description: 'Hook \u753b\u9762\u7f3a\u5931 - \u9700\u8981\u51b2\u7a81\u753b\u9762\u6216\u60ac\u5ff5\u5c55\u793a',
    requiredSlot: '0-3s',
    selectedStrategyId: 'reorder',
    recommendedStrategy: 'reorder',
    status: 'open',
    strategies: [
      { id: 'reorder', name: '\u7ed3\u6784\u91cd\u6392', description: '\u5c06\u573a\u666f\u56fe\u524d\u7f6e\u5e76\u8c03\u6574\u5206\u955c\u987a\u5e8f', available: false, unavailableReason: '\u8bf7\u5728\u65f6\u95f4\u7ebf\u4e2d\u624b\u52a8\u8c03\u6574' },
      { id: 'aigc', name: 'AIGC \u751f\u6210', description: '\u751f\u6210\u60ac\u5ff5\u5c01\u9762\u56fe\u5e76\u914d\u5408\u5feb\u901f\u7f29\u653e', available: false, unavailableReason: '\u672a\u914d\u7f6e\u751f\u6210\u670d\u52a1' },
      { id: 'packaging', name: '\u5305\u88c5\u8865\u5168', description: '\u4f7f\u7528\u5927\u6807\u9898\u5b57\u548c\u5f3a\u8c03\u52a8\u753b\u586b\u8865\u753b\u9762', available: true },
    ],
  },
  {
    id: 'gap-cta',
    segmentId: 'seg-cta',
    severity: 'warning',
    description: 'CTA \u80cc\u666f\u56fe\u7f3a\u5931 - \u9700\u8981\u8f6c\u5316\u573a\u666f\u6216\u4ef7\u683c\u89d2\u6807',
    requiredSlot: '24-35s',
    selectedStrategyId: 'packaging',
    recommendedStrategy: 'packaging',
    status: 'open',
    strategies: [
      { id: 'packaging', name: '\u5305\u88c5\u8865\u5168', description: '\u7528\u4ef7\u683c\u5361\u548c\u7bad\u5934\u5f3a\u5316\u8f6c\u5316', available: true },
      { id: 'recompose', name: '\u7d20\u6750\u91cd\u7ec4', description: '\u590d\u7528\u4ea7\u54c1\u56fe\u5e76\u88c1\u5207\u51fa\u8d2d\u4e70\u6309\u94ae\u533a', available: false, unavailableReason: '\u9700\u8981\u89c6\u9891\u7d20\u6750' },
      { id: 'aigc', name: 'AIGC \u751f\u6210', description: '\u751f\u6210\u4e00\u5f20\u8d2d\u4e70\u573a\u666f\u80cc\u666f\u56fe', available: false, unavailableReason: '\u672a\u914d\u7f6e\u751f\u6210\u670d\u52a1' },
    ],
  },
];
