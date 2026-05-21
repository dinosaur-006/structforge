import type { Asset } from '../shared/types';

export const mockAssets: Asset[] = [
  { id: 'asset-product-close', name: '\u8033\u673a\u7279\u5199.jpg', type: 'image', tag: '\u4ea7\u54c1\u7279\u5199', matchStatus: 'matched', matchScore: 92, color: '#5C8B67' },
  { id: 'asset-desk', name: '\u529e\u516c\u684c\u573a\u666f.jpg', type: 'image', tag: '\u573a\u666f', matchStatus: 'partial', matchScore: 68, color: '#C87D53' },
  { id: 'asset-subway', name: '\u901a\u52e4\u5730\u94c1.mp4', type: 'video', tag: '\u75db\u70b9\u573a\u666f', matchStatus: 'matched', matchScore: 84, color: '#D4A24E' },
  { id: 'asset-unbox', name: '\u5f00\u76d2\u7247\u6bb5.mp4', type: 'video', tag: '\u4ea7\u54c1\u5f15\u5165', matchStatus: 'matched', matchScore: 88, color: '#4A8C6F' },
  { id: 'asset-price-card', name: '\u4ef7\u683c\u5361.png', type: 'image', tag: 'CTA', matchStatus: 'unmatched', matchScore: 42, color: '#C85555' },
];
