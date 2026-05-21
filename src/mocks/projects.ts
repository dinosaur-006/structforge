import type { Project } from '../shared/types';

export const mockProjects: Project[] = [
  {
    id: 'proj-1',
    name: '\u8033\u673a\u65b0\u54c1\u63a8\u5e7f',
    description: '\u9ad8\u70b9\u51fb\u7248\u7ed3\u6784\u8fc1\u79fb',
    status: 'editing',
    updatedAt: '2026-05-21T03:00:00Z',
  },
  {
    id: 'proj-2',
    name: '\u62a4\u80a4\u54c1\u79cb\u5b63\u4e0a\u65b0',
    description: '\u4fdd\u5b88\u4fee\u590d\u7248',
    status: 'analyzing',
    updatedAt: '2026-05-20T16:30:00Z',
  },
  {
    id: 'proj-3',
    name: '\u5065\u8eab\u8bfe\u7a0b\u8f6c\u5316\u89c6\u9891',
    description: '\u5f3a CTA \u7248',
    status: 'completed',
    updatedAt: '2026-05-19T09:00:00Z',
  },
];
