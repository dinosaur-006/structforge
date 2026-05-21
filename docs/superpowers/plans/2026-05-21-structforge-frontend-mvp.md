# StructForge Frontend Mock MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete StructForge frontend Mock MVP with projects, analysis, migration, results, shared state, responsive behavior, and global product states.

**Architecture:** Create a Vite React app with route-level pages, feature folders, shared UI primitives, central Zustand slices, and typed mock data. UI components read from typed store actions so mock behavior can be replaced by API calls without changing page composition.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS 3.4, react-router-dom v6, Zustand, lucide-react, Recharts, dnd-kit, Vitest, Testing Library.

---

## File Structure Map

Create this structure under `D:\爆款结构迁移引擎`:

```text
src/
  App.tsx
  main.tsx
  router.tsx
  index.css
  components/
    ErrorBoundary.tsx
    Version.tsx
    layout/AppLayout.tsx
    ui/Badge.tsx
    ui/Button.tsx
    ui/Drawer.tsx
    ui/EmptyState.tsx
    ui/ErrorAlert.tsx
    ui/Modal.tsx
    ui/Skeleton.tsx
    ui/Tabs.tsx
    ui/Toast.tsx
    ui/TopProgress.tsx
    analyze/AnalysisProgress.tsx
    analyze/HealthAssessment.tsx
    analyze/PackagingStructure.tsx
    analyze/RhythmStructure.tsx
    analyze/ScriptStructure.tsx
    analyze/StructureTabs.tsx
    analyze/VideoInfoCard.tsx
    analyze/VideoUploader.tsx
    migrate/AssetPanel.tsx
    migrate/GapPanel.tsx
    migrate/SegmentBlock.tsx
    migrate/SegmentDrawer.tsx
    migrate/TimelineEditor.tsx
    result/CompareRadar.tsx
    result/ExportDialog.tsx
    result/ResultTimeline.tsx
    result/VersionTabs.tsx
    result/VideoPlayer.tsx
  mocks/
    analysisResult.ts
    assets.ts
    gaps.ts
    projects.ts
    versions.ts
  pages/
    AnalyzePage.tsx
    MigratePage.tsx
    NotFoundPage.tsx
    ProjectListPage.tsx
    ResultPage.tsx
  shared/
    copy.ts
    format.ts
    status.ts
    types.ts
  store/
    index.ts
  test/
    setup.ts
```

Primary responsibilities:

- `shared/types.ts`: all domain types used by mocks, stores, pages, and components.
- `store/index.ts`: all Zustand slices and actions.
- `mocks/*`: deterministic data for projects, analysis, assets, gaps, and versions.
- `components/ui/*`: reusable primitives with no page-specific data.
- `components/analyze/*`, `components/migrate/*`, `components/result/*`: feature components.
- `pages/*`: route-level composition and guards.

---

### Task 1: Scaffold Project And Install Dependencies

**Files:**
- Create: `package.json`
- Create: `index.html`
- Create: `tsconfig.json`
- Create: `tsconfig.node.json`
- Create: `vite.config.ts`
- Create: `postcss.config.js`
- Create: `tailwind.config.js`
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `src/index.css`
- Create: `src/test/setup.ts`

- [ ] **Step 1: Initialize package metadata**

Run:

```powershell
npm create vite@latest . -- --template react-ts
```

Expected: Vite creates a React TypeScript project in the workspace root.

- [ ] **Step 2: Install runtime dependencies**

Run:

```powershell
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities @vitejs/plugin-react lucide-react recharts react-router-dom zustand
```

Expected: dependencies are added to `package.json`.

- [ ] **Step 3: Install styling and test dependencies**

Run:

```powershell
npm install -D tailwindcss@3.4.17 postcss autoprefixer vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Expected: dev dependencies are added to `package.json`.

- [ ] **Step 4: Configure Tailwind**

Run:

```powershell
npx tailwindcss init -p
```

Expected: `tailwind.config.js` and `postcss.config.js` exist.

- [ ] **Step 5: Replace `tailwind.config.js`**

Use:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#7C3AED',
        accent: '#06B6D4',
        surface: '#0F0F23',
        card: '#1A1A2E',
        border: '#2D2D44',
        sidebar: '#13132A',
        'text-primary': '#F1F5F9',
        'text-secondary': '#94A3B8',
        success: '#10B981',
        warning: '#F59E0B',
        error: '#EF4444',
      },
      boxShadow: {
        glow: '0 4px 24px rgba(124, 58, 237, 0.15)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular'],
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 6: Replace `vite.config.ts`**

Use:

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
```

- [ ] **Step 7: Create test setup**

Use `src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 8: Replace global CSS**

Use `src/index.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: dark;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

html {
  min-width: 320px;
  background: #0f0f23;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100dvh;
  background: #0f0f23;
  color: #f1f5f9;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: #101026;
}

::-webkit-scrollbar-thumb {
  background: #4c2a86;
  border-radius: 999px;
  border: 2px solid #101026;
}

::-webkit-scrollbar-thumb:hover {
  background: #7c3aed;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 9: Add package scripts**

Ensure `package.json` scripts include:

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 10: Verify scaffold**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite complete successfully.

- [ ] **Step 11: Commit if git exists**

Run:

```powershell
git status --short
```

Expected: if the command reports a repository, commit with:

```powershell
git add .
git commit -m "chore: scaffold structforge frontend"
```

If `git status` reports "not a git repository", continue without committing.

---

### Task 2: Add Domain Types, Copy Constants, Format Helpers, And Mock Data

**Files:**
- Create: `src/shared/types.ts`
- Create: `src/shared/copy.ts`
- Create: `src/shared/format.ts`
- Create: `src/shared/status.ts`
- Create: `src/mocks/projects.ts`
- Create: `src/mocks/analysisResult.ts`
- Create: `src/mocks/assets.ts`
- Create: `src/mocks/gaps.ts`
- Create: `src/mocks/versions.ts`
- Create: `src/shared/format.test.ts`

- [ ] **Step 1: Write format tests**

Use `src/shared/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatDuration, formatRelativeTime, scoreTone } from './format';

describe('format helpers', () => {
  it('formats durations in seconds', () => {
    expect(formatDuration(35)).toBe('35s');
    expect(formatDuration(3.5)).toBe('3.5s');
  });

  it('formats known relative times', () => {
    const now = new Date('2026-05-21T12:00:00Z');
    expect(formatRelativeTime('2026-05-21T10:00:00Z', now)).toBe('2h ago');
    expect(formatRelativeTime('2026-05-20T12:00:00Z', now)).toBe('1d ago');
  });

  it('maps scores to semantic tones', () => {
    expect(scoreTone(87)).toBe('success');
    expect(scoreTone(72)).toBe('warning');
    expect(scoreTone(48)).toBe('error');
  });
});
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
npm run test -- src/shared/format.test.ts
```

Expected: FAIL because helper files do not exist.

- [ ] **Step 3: Create domain types**

Use `src/shared/types.ts`:

```ts
export type ProjectStatus = 'draft' | 'analyzing' | 'editing' | 'rendering' | 'completed';
export type SegmentType = 'hook' | 'pain' | 'product' | 'proof' | 'cta';
export type AssetType = 'image' | 'video';
export type MatchStatus = 'matched' | 'partial' | 'unmatched';
export type HealthTone = 'success' | 'warning' | 'error';
export type GapSeverity = 'critical' | 'warning';
export type GapStatus = 'open' | 'fixed';
export type SourceType = 'original' | 'reorder' | 'aigc' | 'packaging';

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
```

- [ ] **Step 4: Create copy constants using Unicode escapes**

Use `src/shared/copy.ts`:

```ts
export const copy = {
  appName: 'StructForge',
  navAnalyze: '\u6837\u4f8b\u5206\u6790\u53f0',
  navProjects: '\u9879\u76ee\u5217\u8868',
  projectsTitle: '\u6211\u7684\u9879\u76ee',
  newProject: '\u65b0\u5efa\u9879\u76ee',
  analyzeTitle: '\u6837\u4f8b\u5206\u6790\u53f0',
  analyzeSubtitle: '\u4e0a\u4f20\u6837\u4f8b\u89c6\u9891\uff0cAI \u5c06\u81ea\u52a8\u62c6\u89e3\u5176\u7ed3\u6784\u57fa\u56e0',
  exportJson: '\u5bfc\u51fa JSON',
  nextStep: '\u4e0b\u4e00\u6b65',
  migrateTitle: '\u7ed3\u6784\u8fc1\u79fb\u53f0',
  resultTitle: '\u7ed3\u679c\u5c55\u793a\u53f0',
  previewResult: '\u9884\u89c8\u7ed3\u679c',
  generateVideo: '\u751f\u6210\u89c6\u9891',
  exportVideo: '\u5bfc\u51fa\u89c6\u9891',
  exportReport: '\u5bfc\u51fa\u62a5\u544a',
};
```

- [ ] **Step 5: Create format helpers**

Use `src/shared/format.ts`:

```ts
import type { HealthTone } from './types';

export function formatDuration(seconds: number): string {
  return Number.isInteger(seconds) ? `${seconds}s` : `${seconds.toFixed(1)}s`;
}

export function formatRelativeTime(value: string, now = new Date()): string {
  const diff = Math.max(0, now.getTime() - new Date(value).getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${Math.max(1, minutes)}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function scoreTone(score: number): HealthTone {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'error';
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
```

- [ ] **Step 6: Create status metadata**

Use `src/shared/status.ts`:

```ts
import type { ProjectStatus, SourceType } from './types';

export const projectStatusMeta: Record<ProjectStatus, { label: string; tone: 'success' | 'warning' | 'error' | 'info' }> = {
  draft: { label: '\u8349\u7a3f', tone: 'info' },
  analyzing: { label: '\u5206\u6790\u4e2d', tone: 'warning' },
  editing: { label: '\u7f16\u8f91\u4e2d', tone: 'info' },
  rendering: { label: '\u6e32\u67d3\u4e2d', tone: 'warning' },
  completed: { label: '\u5df2\u5b8c\u6210', tone: 'success' },
};

export const sourceMeta: Record<SourceType, { label: string; colorClass: string }> = {
  original: { label: '\u539f\u7d20\u6750', colorClass: 'bg-success/25 text-success border-success/40' },
  reorder: { label: '\u7ed3\u6784\u91cd\u6392', colorClass: 'bg-warning/25 text-warning border-warning/40' },
  aigc: { label: 'AIGC \u751f\u6210', colorClass: 'bg-accent/25 text-accent border-accent/40' },
  packaging: { label: '\u5305\u88c5\u8865\u5168', colorClass: 'bg-primary/25 text-purple-200 border-primary/40' },
};
```

- [ ] **Step 7: Create mock projects**

Use `src/mocks/projects.ts`:

```ts
import type { Project } from '../shared/types';

export const mockProjects: Project[] = [
  { id: 'proj-1', name: '\u8033\u673a\u65b0\u54c1\u63a8\u5e7f', description: '\u9ad8\u70b9\u51fb\u7248\u7ed3\u6784\u8fc1\u79fb', status: 'editing', updatedAt: '2026-05-21T03:00:00Z' },
  { id: 'proj-2', name: '\u62a4\u80a4\u54c1\u79cb\u5b63\u4e0a\u65b0', description: '\u4fdd\u5b88\u4fee\u590d\u7248', status: 'analyzing', updatedAt: '2026-05-20T16:30:00Z' },
  { id: 'proj-3', name: '\u5065\u8eab\u8bfe\u7a0b\u8f6c\u5316\u89c6\u9891', description: '\u5f3a CTA \u7248', status: 'completed', updatedAt: '2026-05-19T09:00:00Z' },
];
```

- [ ] **Step 8: Create analysis mock data**

Use `src/mocks/analysisResult.ts`:

```ts
import type { VideoStructure } from '../shared/types';

export const mockAnalysisResult: VideoStructure = {
  meta: { duration: 35, resolution: '1080x1920', shots: 12, coverLabel: '\u4ea7\u54c1\u65cb\u8f6c\u7279\u5199' },
  script: [
    { id: 'seg-hook', type: 'hook', label: 'Hook', start: 0, end: 3, duration: 3, goal: 'stop_scroll', copy: '\u4f60\u4ee5\u4e3a\u8fd9\u662f\u666e\u901a\u8033\u673a\uff1f', visual: '\u4ea7\u54c1\u7279\u5199\u65cb\u8f6c + \u5feb\u901f\u7f29\u653e', healthScore: 87 },
    { id: 'seg-pain', type: 'pain', label: '\u75db\u70b9', start: 3, end: 8, duration: 5, goal: 'problem_awareness', copy: '\u901a\u52e4\u566a\u97f3\u8ba9\u4f60\u6bcf\u5929\u90fd\u5f88\u70e6', visual: '\u5730\u94c1\u4eba\u7fa4\u4e0e\u8868\u60c5\u7279\u5199', healthScore: 74 },
    { id: 'seg-product', type: 'product', label: '\u4ea7\u54c1\u5f15\u5165', start: 8, end: 12, duration: 4, goal: 'solution_intro', copy: '\u8fd9\u4e2a\u964d\u566a\u8231\u628a\u58f0\u97f3\u9694\u5f00', visual: '\u8033\u673a\u5f00\u76d2\u4e0e\u964d\u566a\u6ce2\u7eb9', healthScore: 62 },
    { id: 'seg-proof', type: 'proof', label: '\u5356\u70b9\u8bc1\u660e', start: 12, end: 24, duration: 12, goal: 'benefit_proof', copy: '\u53cc\u82af\u7247\u964d\u566a\uff0c\u4eba\u58f0\u4e5f\u80fd\u6e05\u695a', visual: '\u529f\u80fd\u5bf9\u6bd4\u5206\u5c4f\u4e0e\u53c2\u6570\u6807\u7b7e', healthScore: 48 },
    { id: 'seg-cta', type: 'cta', label: 'CTA', start: 24, end: 35, duration: 11, goal: 'conversion', copy: '\u73b0\u5728\u9884\u7ea6\uff0c\u524d 100 \u540d\u9001\u8033\u585e\u5957\u88c5', visual: '\u4ef7\u683c\u5361 + \u8d2d\u4e70\u6309\u94ae\u52a8\u753b', healthScore: 39 },
  ],
  rhythm: [
    { second: 0, cuts: 4, emotion: 0.78 },
    { second: 5, cuts: 5, emotion: 0.71 },
    { second: 10, cuts: 3, emotion: 0.63 },
    { second: 15, cuts: 6, emotion: 0.86 },
    { second: 18, cuts: 8, emotion: 0.92, highlight: true },
    { second: 25, cuts: 4, emotion: 0.74 },
    { second: 35, cuts: 3, emotion: 0.69 },
  ],
  packaging: {
    subtitleStyle: ['\u7c97\u4f53\u65e0\u886c\u7ebf', '\u9ec4\u5b57\u767d\u63cf\u8fb9', '\u5c45\u4e2d\u504f\u4e0b', '\u9ad8\u8986\u76d6\u5bc6\u5ea6'],
    transitions: ['\u786c\u5207 70%', '\u5de6\u6ed1 20%', '\u7f29\u653e 10%'],
    overlays: ['\u4ea7\u54c1\u6807\u7b7e\u8d34\u7eb8', '\u4ef7\u683c\u89d2\u6807', '\u7bad\u5934\u5f3a\u8c03'],
  },
  health: {
    hook_strength: 87,
    product_exposure_timing: 62,
    selling_point_proof: 48,
    pacing_compactness: 81,
    cta_persuasiveness: 39,
    overall: 72,
  },
};
```

- [ ] **Step 9: Create assets, gaps, and versions**

Use `src/mocks/assets.ts`:

```ts
import type { Asset } from '../shared/types';

export const mockAssets: Asset[] = [
  { id: 'asset-product-close', name: '\u8033\u673a\u7279\u5199.jpg', type: 'image', tag: '\u4ea7\u54c1\u7279\u5199', matchStatus: 'matched', matchScore: 92, color: '#7C3AED' },
  { id: 'asset-desk', name: '\u529e\u516c\u684c\u573a\u666f.jpg', type: 'image', tag: '\u573a\u666f', matchStatus: 'partial', matchScore: 68, color: '#06B6D4' },
  { id: 'asset-subway', name: '\u901a\u52e4\u5730\u94c1.mp4', type: 'video', tag: '\u75db\u70b9\u573a\u666f', matchStatus: 'matched', matchScore: 84, color: '#F59E0B' },
  { id: 'asset-unbox', name: '\u5f00\u76d2\u7247\u6bb5.mp4', type: 'video', tag: '\u4ea7\u54c1\u5f15\u5165', matchStatus: 'matched', matchScore: 88, color: '#10B981' },
  { id: 'asset-price-card', name: '\u4ef7\u683c\u5361.png', type: 'image', tag: 'CTA', matchStatus: 'unmatched', matchScore: 42, color: '#EF4444' },
];
```

Use `src/mocks/gaps.ts`:

```ts
import type { MaterialGap } from '../shared/types';

export const mockGaps: MaterialGap[] = [
  {
    id: 'gap-hook',
    segmentId: 'seg-hook',
    severity: 'critical',
    description: 'Hook \u753b\u9762\u7f3a\u5931 - \u9700\u8981\u51b2\u7a81\u753b\u9762\u6216\u60ac\u5ff5\u5c55\u793a',
    requiredSlot: '0-3s',
    selectedStrategyId: 'reorder',
    status: 'open',
    strategies: [
      { id: 'reorder', name: '\u7ed3\u6784\u91cd\u6392', description: '\u5c06\u573a\u666f\u56fe\u524d\u7f6e\u5e76\u8c03\u6574\u5206\u955c\u987a\u5e8f' },
      { id: 'aigc', name: 'AIGC \u751f\u6210', description: '\u751f\u6210\u60ac\u5ff5\u5c01\u9762\u56fe\u5e76\u914d\u5408\u5feb\u901f\u7f29\u653e' },
      { id: 'packaging', name: '\u5305\u88c5\u8865\u5168', description: '\u4f7f\u7528\u5927\u6807\u9898\u5b57\u548c\u5f3a\u8c03\u52a8\u753b\u586b\u8865\u753b\u9762' },
    ],
  },
  {
    id: 'gap-cta',
    segmentId: 'seg-cta',
    severity: 'warning',
    description: 'CTA \u80cc\u666f\u56fe\u7f3a\u5931 - \u9700\u8981\u8f6c\u5316\u573a\u666f\u6216\u4ef7\u683c\u89d2\u6807',
    requiredSlot: '24-35s',
    selectedStrategyId: 'packaging',
    status: 'open',
    strategies: [
      { id: 'packaging', name: '\u5305\u88c5\u8865\u5168', description: '\u7528\u4ef7\u683c\u5361\u548c\u7bad\u5934\u5f3a\u5316\u8f6c\u5316' },
      { id: 'recompose', name: '\u7d20\u6750\u91cd\u7ec4', description: '\u590d\u7528\u4ea7\u54c1\u56fe\u5e76\u88c1\u5207\u51fa\u8d2d\u4e70\u6309\u94ae\u533a' },
      { id: 'aigc', name: 'AIGC \u751f\u6210', description: '\u751f\u6210\u4e00\u5f20\u8d2d\u4e70\u573a\u666f\u80cc\u666f\u56fe' },
    ],
  },
];
```

Use `src/mocks/versions.ts`:

```ts
import type { ResultVersion } from '../shared/types';

const baseTimeline = [
  { id: 'r-hook', label: 'Hook', start: 0, end: 3, source: 'original' as const },
  { id: 'r-pain', label: '\u75db\u70b9', start: 3, end: 8, source: 'reorder' as const },
  { id: 'r-product', label: '\u4ea7\u54c1', start: 8, end: 12, source: 'original' as const },
  { id: 'r-proof-a', label: '\u5356\u70b9 A', start: 12, end: 20, source: 'aigc' as const },
  { id: 'r-proof-b', label: '\u5356\u70b9 B', start: 20, end: 26, source: 'original' as const },
  { id: 'r-cta', label: 'CTA', start: 26, end: 35, source: 'packaging' as const },
];

export const mockVersions: ResultVersion[] = [
  {
    id: 'original',
    name: '\u539f\u7248',
    score: 52,
    metrics: { scoreDelta: 0, hookAdvance: '0s', exposureAdvance: '0s', wasteReduction: '0%', ctaDuration: '2.0s' },
    health: { hook_strength: 42, product_exposure_timing: 48, selling_point_proof: 46, pacing_compactness: 55, cta_persuasiveness: 39, overall: 52 },
    timeline: baseTimeline.map((segment) => ({ ...segment, source: 'original' })),
  },
  {
    id: 'safe-fix',
    name: '\u4fdd\u5b88\u4fee\u590d',
    score: 68,
    metrics: { scoreDelta: 16, hookAdvance: '1.2s', exposureAdvance: '2.0s', wasteReduction: '21%', ctaDuration: '3.2s' },
    health: { hook_strength: 68, product_exposure_timing: 64, selling_point_proof: 61, pacing_compactness: 70, cta_persuasiveness: 58, overall: 68 },
    timeline: baseTimeline,
  },
  {
    id: 'strong-hook',
    name: 'Strong Hook',
    score: 81,
    metrics: { scoreDelta: 29, hookAdvance: '2.1s', exposureAdvance: '4.5s', wasteReduction: '38%', ctaDuration: '4.0s' },
    health: { hook_strength: 91, product_exposure_timing: 80, selling_point_proof: 74, pacing_compactness: 85, cta_persuasiveness: 75, overall: 81 },
    timeline: baseTimeline,
  },
  {
    id: 'strong-conversion',
    name: '\u5f3a\u8f6c\u5316',
    score: 79,
    metrics: { scoreDelta: 27, hookAdvance: '1.8s', exposureAdvance: '3.9s', wasteReduction: '34%', ctaDuration: '5.1s' },
    health: { hook_strength: 82, product_exposure_timing: 76, selling_point_proof: 72, pacing_compactness: 78, cta_persuasiveness: 88, overall: 79 },
    timeline: baseTimeline.map((segment) => segment.id === 'r-cta' ? { ...segment, end: 35, source: 'packaging' } : segment),
  },
];
```

- [ ] **Step 10: Run format tests**

Run:

```powershell
npm run test -- src/shared/format.test.ts
```

Expected: PASS.

- [ ] **Step 11: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 3: Build Zustand Store

**Files:**
- Create: `src/store/index.ts`
- Create: `src/store/index.test.ts`

- [ ] **Step 1: Write store behavior tests**

Use `src/store/index.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from './index';

describe('app store', () => {
  beforeEach(() => {
    useAppStore.getState().resetForTest();
  });

  it('creates and removes projects', () => {
    const id = useAppStore.getState().addProject('Launch Clip', 'Draft');
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(true);
    useAppStore.getState().removeProject(id);
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(false);
  });

  it('updates a segment and supports undo redo', () => {
    useAppStore.getState().loadProjectStructure('proj-1');
    useAppStore.getState().updateSegment('seg-hook', { duration: 4, end: 4 });
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
    useAppStore.getState().undo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(3);
    useAppStore.getState().redo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
  });

  it('fixes gaps asynchronously', async () => {
    vi.useFakeTimers();
    const promise = useAppStore.getState().fixGaps();
    await vi.advanceTimersByTimeAsync(2100);
    await promise;
    expect(useAppStore.getState().gaps.every((gap) => gap.status === 'fixed')).toBe(true);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run store test and verify failure**

Run:

```powershell
npm run test -- src/store/index.test.ts
```

Expected: FAIL because `src/store/index.ts` does not exist.

- [ ] **Step 3: Create store**

Implement `src/store/index.ts` with:

```ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { mockAnalysisResult } from '../mocks/analysisResult';
import { mockAssets } from '../mocks/assets';
import { mockGaps } from '../mocks/gaps';
import { mockProjects } from '../mocks/projects';
import { mockVersions } from '../mocks/versions';
import type { MaterialGap, Project, ResultVersion, ScriptSegment, ToastMessage, VideoStructure } from '../shared/types';

interface AppState {
  sidebarCollapsed: boolean;
  mobileSidebarOpen: boolean;
  routeLoading: boolean;
  projects: Project[];
  videoFile: File | null;
  isAnalyzing: boolean;
  progress: number;
  stage: string;
  analysisResult: VideoStructure | null;
  currentStructure: VideoStructure | null;
  assets: typeof mockAssets;
  gaps: MaterialGap[];
  isFixing: boolean;
  selectedSegmentId: string | null;
  drawerOpen: boolean;
  history: VideoStructure[];
  future: VideoStructure[];
  versions: ResultVersion[];
  currentVersionId: string;
  isExporting: boolean;
  toasts: ToastMessage[];
  toggleSidebar: () => void;
  setMobileSidebarOpen: (open: boolean) => void;
  setRouteLoading: (loading: boolean) => void;
  addProject: (name: string, description: string) => string;
  removeProject: (id: string) => void;
  findProject: (id: string) => Project | undefined;
  setVideoFile: (file: File | null) => void;
  startAnalysis: () => Promise<void>;
  resetAnalysis: () => void;
  completeAnalysisNow: () => void;
  loadProjectStructure: (projectId: string) => void;
  updateSegment: (id: string, changes: Partial<ScriptSegment>) => void;
  reorderSegments: (activeId: string, overId: string) => void;
  selectSegment: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
  undo: () => void;
  redo: () => void;
  resetStructure: () => void;
  fixGaps: () => Promise<void>;
  setVersion: (id: string) => void;
  exportResult: () => Promise<void>;
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  resetForTest: () => void;
}
```

The action implementation must:

- Persist only `sidebarCollapsed`, `projects`, `currentStructure`, and `currentVersionId`.
- Keep `File`, timers, toasts, and loading flags outside persisted state.
- Use `crypto.randomUUID()` when available and a `Date.now()` fallback.
- Push `currentStructure` into `history` before mutations.
- Cap `history` at 20 entries.
- Set all gaps to `fixed` inside `fixGaps` after a 2000ms timeout.

- [ ] **Step 4: Run store tests**

Run:

```powershell
npm run test -- src/store/index.test.ts
```

Expected: PASS.

- [ ] **Step 5: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 4: Build Shared UI Components

**Files:**
- Create: `src/components/ui/Button.tsx`
- Create: `src/components/ui/Badge.tsx`
- Create: `src/components/ui/Modal.tsx`
- Create: `src/components/ui/Drawer.tsx`
- Create: `src/components/ui/EmptyState.tsx`
- Create: `src/components/ui/ErrorAlert.tsx`
- Create: `src/components/ui/Skeleton.tsx`
- Create: `src/components/ui/Tabs.tsx`
- Create: `src/components/ui/Toast.tsx`
- Create: `src/components/ui/TopProgress.tsx`
- Create: `src/components/ErrorBoundary.tsx`
- Create: `src/components/Version.tsx`
- Create: `src/components/ui/Button.test.tsx`

- [ ] **Step 1: Write a button render test**

Use `src/components/ui/Button.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders accessible button text', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/components/ui/Button.test.tsx
```

Expected: FAIL because `Button.tsx` does not exist.

- [ ] **Step 3: Create UI primitives**

Implement these component APIs exactly:

```ts
// Button.tsx
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'icon';
}
```

```ts
// Badge.tsx
export interface BadgeProps {
  children: React.ReactNode;
  tone?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  className?: string;
}
```

```ts
// Modal.tsx and Drawer.tsx
export interface OverlayProps {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  footer?: React.ReactNode;
}
```

```ts
// Tabs.tsx
export interface TabItem<T extends string> {
  id: T;
  label: string;
}
export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}
```

Rules:

- Button heights are at least `h-11`.
- Icon-only buttons require `aria-label` from caller.
- Modal and Drawer render nothing when `open` is false.
- Modal and Drawer have a strong dark scrim, close button, focusable content, and Escape key close.
- Toast uses `aria-live="polite"` and reads messages from `useAppStore`.
- `TopProgress` animates only transform/opacity and accepts `active: boolean`.

- [ ] **Step 4: Run shared component test**

Run:

```powershell
npm run test -- src/components/ui/Button.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 5: Build Routing And App Layout

**Files:**
- Create: `src/router.tsx`
- Create: `src/components/layout/AppLayout.tsx`
- Create: `src/pages/NotFoundPage.tsx`
- Modify: `src/App.tsx`
- Modify: `src/main.tsx`
- Create: `src/components/layout/AppLayout.test.tsx`

- [ ] **Step 1: Write layout test**

Use `src/components/layout/AppLayout.test.tsx`:

```tsx
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AppLayout } from './AppLayout';

describe('AppLayout', () => {
  it('renders navigation and child content', () => {
    render(
      <MemoryRouter initialEntries={['/projects']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/projects" element={<div>Projects body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('StructForge')).toBeInTheDocument();
    expect(screen.getByText('Projects body')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/components/layout/AppLayout.test.tsx
```

Expected: FAIL because layout does not exist.

- [ ] **Step 3: Create route shell**

`src/router.tsx` must:

- Use `createBrowserRouter`.
- Redirect `/` to `/projects`.
- Lazy load four pages with `React.lazy`.
- Use `AppLayout` as route parent.
- Route `*` to `NotFoundPage`.

`src/App.tsx` must render:

```tsx
import { RouterProvider } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Toast } from './components/ui/Toast';
import { router } from './router';

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
      <Toast />
    </ErrorBoundary>
  );
}
```

`src/main.tsx` must render `App` inside `React.StrictMode`.

- [ ] **Step 4: Create `AppLayout`**

Layout requirements:

- Sidebar expanded width `w-60`, collapsed width `w-16`.
- Uses `Wand2`, `FlaskConical`, `FolderOpen`, `User`, `Settings`, `ChevronLeft`, `ChevronRight`, `Menu`.
- Active nav uses purple left border and background highlight.
- Mobile menu button appears below `md`.
- Mobile sidebar uses overlay scrim and closes on nav click.
- Main content renders `Outlet` inside `Suspense` with `Skeleton`.

- [ ] **Step 5: Create route-level empty pages**

Create temporary page components with headings:

- `ProjectListPage`: project-list title from `copy`.
- `AnalyzePage`: analyze title from `copy`.
- `MigratePage`: migrate title from `copy`.
- `ResultPage`: result title from `copy`.
- `NotFoundPage`: message plus button to `/projects`.

- [ ] **Step 6: Run layout test**

Run:

```powershell
npm run test -- src/components/layout/AppLayout.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 6: Build Projects Page

**Files:**
- Modify: `src/pages/ProjectListPage.tsx`
- Create: `src/pages/ProjectListPage.test.tsx`

- [ ] **Step 1: Write project page test**

Use `src/pages/ProjectListPage.test.tsx`:

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import ProjectListPage from './ProjectListPage';
import { useAppStore } from '../store';

describe('ProjectListPage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('creates a project from the dialog', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><ProjectListPage /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: /\u65b0\u5efa\u9879\u76ee/ }));
    await user.type(screen.getByLabelText(/\u9879\u76ee\u540d\u79f0/), 'New Clip');
    await user.click(screen.getByRole('button', { name: /\u521b\u5efa/ }));
    expect(screen.getByText('New Clip')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/pages/ProjectListPage.test.tsx
```

Expected: FAIL because the page is still temporary.

- [ ] **Step 3: Implement `ProjectListPage`**

Page must include:

- Header with `copy.projectsTitle`.
- Primary button with `copy.newProject` and `Plus`.
- Create modal with visible labels for project name and description.
- Project grid `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`.
- Cards with video icon area, status badge, relative updated time, description, and actions.
- Delete button with `Trash2` and `aria-label`.
- Empty state when project list is empty.
- Card click uses `navigate('/migrate/' + project.id)`.

Use these labels:

```ts
const labels = {
  name: '\u9879\u76ee\u540d\u79f0',
  description: '\u63cf\u8ff0',
  create: '\u521b\u5efa',
  cancel: '\u53d6\u6d88',
  emptyTitle: '\u8fd8\u6ca1\u6709\u9879\u76ee',
  emptyDescription: '\u521b\u5efa\u7b2c\u4e00\u4e2a\u7ed3\u6784\u8fc1\u79fb\u9879\u76ee',
};
```

- [ ] **Step 4: Run page test**

Run:

```powershell
npm run test -- src/pages/ProjectListPage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 7: Build Analyze Upload And Progress Flow

**Files:**
- Modify: `src/pages/AnalyzePage.tsx`
- Create: `src/components/analyze/VideoUploader.tsx`
- Create: `src/components/analyze/AnalysisProgress.tsx`
- Create: `src/pages/AnalyzePage.test.tsx`

- [ ] **Step 1: Write analyze flow test**

Use `src/pages/AnalyzePage.test.tsx`:

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AnalyzePage from './AnalyzePage';
import { useAppStore } from '../store';

describe('AnalyzePage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('rejects non-video files', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><AnalyzePage /></MemoryRouter>);
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);
    await user.upload(input, new File(['x'], 'notes.txt', { type: 'text/plain' }));
    expect(screen.getByText(/\u4ec5\u652f\u6301/)).toBeInTheDocument();
  });

  it('runs mock analysis', async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<MemoryRouter><AnalyzePage /></MemoryRouter>);
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);
    await user.upload(input, new File(['video'], 'sample.mp4', { type: 'video/mp4' }));
    await user.click(screen.getByRole('button', { name: /\u5f00\u59cb\u5206\u6790/ }));
    await vi.advanceTimersByTimeAsync(6500);
    expect(screen.getByText(/\u811a\u672c\u7ed3\u6784/)).toBeInTheDocument();
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/pages/AnalyzePage.test.tsx
```

Expected: FAIL because upload flow is absent.

- [ ] **Step 3: Implement `VideoUploader`**

Component props:

```ts
interface VideoUploaderProps {
  file: File | null;
  onFile: (file: File | null) => void;
  onStart: () => void;
  disabled?: boolean;
}
```

Behavior:

- Hidden input accepts `video/mp4,video/quicktime,video/*`.
- Visible drop zone has `aria-label="\u9009\u62e9\u89c6\u9891"`.
- Rejects files whose `type` does not start with `video/`.
- Shows an `ErrorAlert` with text containing `\u4ec5\u652f\u6301`.
- Uploaded state shows filename, mocked metadata `35s`, `1080x1920`, `42MB`.
- Buttons: reupload and start analysis.

- [ ] **Step 4: Implement `AnalysisProgress`**

Props:

```ts
interface AnalysisProgressProps {
  progress: number;
  stage: string;
}
```

Render:

- Stage icon from `ScanSearch`, `Images`, `SplitSquareHorizontal`, `Activity`.
- Percent number on the right.
- Gradient progress bar using transform scaleX.
- Detail line with the current stage.

- [ ] **Step 5: Implement `AnalyzePage` shell**

Page uses:

- `copy.analyzeTitle`, `copy.analyzeSubtitle`, `copy.exportJson`, `copy.nextStep`.
- Store state: `videoFile`, `isAnalyzing`, `progress`, `stage`, `analysisResult`.
- `completeAnalysisNow` for development path when needed.
- `navigate('/migrate/proj-1')` on next-step after loading project structure.

- [ ] **Step 6: Run analyze test**

Run:

```powershell
npm run test -- src/pages/AnalyzePage.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 8: Build Analyze Result Visualizations

**Files:**
- Create: `src/components/analyze/VideoInfoCard.tsx`
- Create: `src/components/analyze/StructureTabs.tsx`
- Create: `src/components/analyze/ScriptStructure.tsx`
- Create: `src/components/analyze/RhythmStructure.tsx`
- Create: `src/components/analyze/PackagingStructure.tsx`
- Create: `src/components/analyze/HealthAssessment.tsx`
- Modify: `src/pages/AnalyzePage.tsx`

- [ ] **Step 1: Create `VideoInfoCard`**

Props:

```ts
interface VideoInfoCardProps {
  structure: VideoStructure;
}
```

Render four cards: duration, resolution, shots, cover. Use `Clock`, `Ruler`, `Clapperboard`, `Image`.

- [ ] **Step 2: Create `StructureTabs`**

Tabs:

```ts
type AnalyzeTab = 'script' | 'rhythm' | 'packaging' | 'health';
```

Labels:

- `\u811a\u672c\u7ed3\u6784`
- `\u8282\u594f\u7ed3\u6784`
- `\u5305\u88c5\u7ed3\u6784`
- `\u5065\u5eb7\u5ea6`

Use local `useState<AnalyzeTab>('script')`.

- [ ] **Step 3: Create `ScriptStructure`**

Props:

```ts
interface ScriptStructureProps {
  segments: ScriptSegment[];
}
```

Behavior:

- Compute total duration from segments.
- Segment width = `(duration / total) * 100`.
- Use color classes by segment type.
- Click segment to set selected ID.
- Detail panel displays selected segment goal, copy, visual, and health score.

- [ ] **Step 4: Create `RhythmStructure`**

Use `ResponsiveContainer`, `AreaChart`, `Area`, `XAxis`, `YAxis`, `Tooltip`, `CartesianGrid`.

Rules:

- Minimum chart height 280px.
- Area fill gradient from primary to accent.
- Stat cards show average shot length `2.2s`, climax `18.0s`, emotion peak `0.92`.

- [ ] **Step 5: Create `PackagingStructure`**

Render three cards with `Type`, `Clapperboard`, and `Sticker` icons. Each card maps string arrays into readable rows.

- [ ] **Step 6: Create `HealthAssessment`**

Use `ResponsiveContainer`, `RadarChart`, `PolarGrid`, `PolarAngleAxis`, `Radar`.

Map health keys to labels:

```ts
const healthLabels = {
  hook_strength: 'Hook',
  product_exposure_timing: 'Exposure',
  selling_point_proof: 'Proof',
  pacing_compactness: 'Pacing',
  cta_persuasiveness: 'CTA',
  overall: 'Overall',
};
```

Right side renders score cards using `scoreTone`.

- [ ] **Step 7: Wire result components into `AnalyzePage`**

When `analysisResult` exists, render `VideoInfoCard` and `StructureTabs`.

- [ ] **Step 8: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 9: Build Migration Page, Asset Panel, Timeline, Drawer, And History

**Files:**
- Modify: `src/pages/MigratePage.tsx`
- Create: `src/components/migrate/AssetPanel.tsx`
- Create: `src/components/migrate/SegmentBlock.tsx`
- Create: `src/components/migrate/TimelineEditor.tsx`
- Create: `src/components/migrate/SegmentDrawer.tsx`
- Create: `src/pages/MigratePage.test.tsx`

- [ ] **Step 1: Write migration route test**

Use `src/pages/MigratePage.test.tsx`:

```tsx
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import MigratePage from './MigratePage';
import { useAppStore } from '../store';

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/migrate/:projectId" element={<MigratePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('MigratePage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('shows missing project state', () => {
    renderRoute('/migrate/missing');
    expect(screen.getByText(/\u9879\u76ee\u4e0d\u5b58\u5728/)).toBeInTheDocument();
  });

  it('edits a segment through the drawer', async () => {
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');
    await user.click(screen.getByRole('button', { name: /Hook/ }));
    await user.clear(screen.getByLabelText(/\u65f6\u957f/));
    await user.type(screen.getByLabelText(/\u65f6\u957f/), '4');
    await user.click(screen.getByRole('button', { name: /\u5e94\u7528\u66f4\u6539/ }));
    expect(screen.getByText('4s')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/pages/MigratePage.test.tsx
```

Expected: FAIL because migration UI is absent.

- [ ] **Step 3: Implement route guard and page shell**

`MigratePage` must:

- Read `projectId` from params.
- Find project in store.
- Render `ErrorAlert` with title `\u9879\u76ee\u4e0d\u5b58\u5728` for missing IDs.
- Call `loadProjectStructure(projectId)` in an effect when project exists.
- Header includes project name, preview-result button, generate-video button.
- Generate-video button navigates to `/result/${projectId}`.

- [ ] **Step 4: Implement `AssetPanel`**

Props:

```ts
interface AssetPanelProps {
  assets: Asset[];
}
```

Render:

- Upload area with `Upload`.
- Empty state if no assets.
- Asset cards with `Image` or `Film`, tag, match badge, and score.
- Wrap cards with dnd-kit draggable attributes.

- [ ] **Step 5: Implement `SegmentBlock`**

Props:

```ts
interface SegmentBlockProps {
  segment: ScriptSegment;
  hasGap: boolean;
  onSelect: (id: string) => void;
}
```

Render as a button with:

- Label.
- Duration using `formatDuration`.
- Health score.
- Lock icon when locked.
- Alert marker when `hasGap`.
- Health background from `scoreTone`.

- [ ] **Step 6: Implement `TimelineEditor`**

Use dnd-kit:

- `DndContext`.
- `SortableContext`.
- `arrayMove` via store `reorderSegments`.
- Horizontal desktop layout and mobile horizontal scroll.
- Time ruler from `0` to total duration in 5-second steps.

- [ ] **Step 7: Implement `SegmentDrawer`**

Drawer contains labeled controls:

- Segment type select.
- Duration number input labeled `\u65f6\u957f`.
- Script textarea.
- Visual textarea.
- Asset select.
- Subtitle select.
- Transition select.
- BGM checkbox.
- Lock checkbox.
- Apply button labeled `\u5e94\u7528\u66f4\u6539`.

On apply, call `updateSegment(selectedId, changes)` and close drawer.

- [ ] **Step 8: Add toolbar actions**

Toolbar buttons:

- Save: add success toast.
- Undo: call `undo`.
- Redo: call `redo`.
- Reset: call `resetStructure`.
- Style select: local state with fast, conversion, premium.

- [ ] **Step 9: Run migration test**

Run:

```powershell
npm run test -- src/pages/MigratePage.test.tsx
```

Expected: PASS.

- [ ] **Step 10: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 10: Build Gap Panel And Repair Simulation

**Files:**
- Create: `src/components/migrate/GapPanel.tsx`
- Modify: `src/pages/MigratePage.tsx`
- Modify: `src/components/migrate/SegmentBlock.tsx`

- [ ] **Step 1: Implement `GapPanel`**

Props:

```ts
interface GapPanelProps {
  gaps: MaterialGap[];
  isFixing: boolean;
  onFixAll: () => void;
}
```

Render:

- Collapsible panel, initially open.
- Header with gap count.
- Each gap shows severity label, description, required slot, selected strategy radio group.
- Strategy radio choices are read from each gap.
- Button text changes from `\u4e00\u952e\u81ea\u52a8\u4fee\u590d` to `\u6b63\u5728\u4fee\u590d`.
- Disable button while fixing or when all gaps are fixed.

- [ ] **Step 2: Wire gap markers**

`SegmentBlock` receives `hasGap` from open gaps only:

```ts
const hasGap = gaps.some((gap) => gap.segmentId === segment.id && gap.status === 'open');
```

- [ ] **Step 3: Wire fix action**

`MigratePage` passes:

```tsx
<GapPanel gaps={gaps} isFixing={isFixing} onFixAll={fixGaps} />
```

After `fixGaps`, store adds a success toast.

- [ ] **Step 4: Manual smoke check**

Run:

```powershell
npm run dev
```

Open `http://127.0.0.1:5173/migrate/proj-1`.

Expected:

- Gap panel is visible.
- Open gap markers appear on affected segments.
- Clicking repair disables button.
- After two seconds markers disappear.

- [ ] **Step 5: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 11: Build Result Page

**Files:**
- Modify: `src/pages/ResultPage.tsx`
- Create: `src/components/result/VersionTabs.tsx`
- Create: `src/components/result/VideoPlayer.tsx`
- Create: `src/components/result/ResultTimeline.tsx`
- Create: `src/components/result/CompareRadar.tsx`
- Create: `src/components/result/ExportDialog.tsx`
- Create: `src/pages/ResultPage.test.tsx`

- [ ] **Step 1: Write result page test**

Use `src/pages/ResultPage.test.tsx`:

```tsx
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import ResultPage from './ResultPage';
import { useAppStore } from '../store';

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/result/:projectId" element={<ResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ResultPage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('switches result versions', async () => {
    const user = userEvent.setup();
    renderRoute('/result/proj-1');
    await user.click(screen.getByRole('button', { name: /Strong Hook/ }));
    expect(screen.getByText(/\+29/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm run test -- src/pages/ResultPage.test.tsx
```

Expected: FAIL because result UI is absent.

- [ ] **Step 3: Implement `ResultPage` guard and shell**

Behavior:

- Read `projectId`.
- Show project-not-found `ErrorAlert` for missing IDs.
- Get current version by `currentVersionId`.
- Header uses `copy.resultTitle`, project name, current version name, export buttons.

- [ ] **Step 4: Implement `VersionTabs`**

Props:

```ts
interface VersionTabsProps {
  versions: ResultVersion[];
  currentId: string;
  onChange: (id: string) => void;
}
```

Render each version as a button with name and score badge.

- [ ] **Step 5: Implement `VideoPlayer`**

Props:

```ts
interface VideoPlayerProps {
  timeline: ResultTimelineSegment[];
}
```

Behavior:

- Black preview area with `Play`, `Pause`, `Volume2`, and `Maximize2`.
- Local progress state from 0 to 100.
- Chapter markers positioned by `segment.start / totalDuration`.
- Segment marker title text appears on hover using `title`.

- [ ] **Step 6: Implement metric panel inside `ResultPage`**

Render:

- Total score delta.
- Hook timing.
- Exposure timing.
- Waste reduction.
- CTA duration.

Use `TrendingUp` and green text for positive changes.

- [ ] **Step 7: Implement `ResultTimeline`**

Props:

```ts
interface ResultTimelineProps {
  segments: ResultTimelineSegment[];
  onSeek: (second: number) => void;
}
```

Render source legend and clickable segment blocks using `sourceMeta`.

- [ ] **Step 8: Implement `CompareRadar`**

Use Recharts radar with:

- Original grey outline from `mockVersions[0].health`.
- Current purple filled radar from selected version.
- Fixed height 320px.

- [ ] **Step 9: Implement `ExportDialog`**

Props:

```ts
interface ExportDialogProps {
  open: boolean;
  isExporting: boolean;
  onClose: () => void;
  onExport: () => void;
}
```

Options:

- MP4 with resolution select 720p/1080p.
- SRT checkbox.
- PDF report checkbox.
- JSON template checkbox.

Export button triggers store `exportResult`.

- [ ] **Step 10: Run result test**

Run:

```powershell
npm run test -- src/pages/ResultPage.test.tsx
```

Expected: PASS.

- [ ] **Step 11: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 12: Add Responsive Polish, Keyboard Shortcuts, And Final Product States

**Files:**
- Modify: `src/components/layout/AppLayout.tsx`
- Modify: `src/pages/MigratePage.tsx`
- Modify: `src/components/migrate/SegmentDrawer.tsx`
- Modify: `src/components/migrate/TimelineEditor.tsx`
- Modify: `src/components/ui/TopProgress.tsx`
- Modify: `src/components/ErrorBoundary.tsx`
- Modify: `src/components/Version.tsx`

- [ ] **Step 1: Add route progress behavior**

In `AppLayout`, set `routeLoading` to true on location change, then false after 250ms. Render:

```tsx
<TopProgress active={routeLoading} />
```

- [ ] **Step 2: Add keyboard shortcuts**

In `MigratePage`, add a keydown listener:

- `Ctrl+Z`: call `undo`.
- `Ctrl+Shift+Z`: call `redo`.
- `Delete`: if `selectedSegmentId` exists and segment is not locked, remove selected segment from structure.

Use `event.preventDefault()` only for handled shortcuts.

- [ ] **Step 3: Make drawer full-screen on mobile**

`Drawer` should apply:

```ts
const panelClass = 'fixed inset-y-0 right-0 z-50 w-full max-w-md md:w-[420px]';
```

For `max-md`, content fills width and height.

- [ ] **Step 4: Stabilize charts and timelines**

Add minimum dimensions:

- Chart wrappers: `min-h-[280px]`.
- Timeline scroll containers: `overflow-x-auto`.
- Segment blocks: `min-w-[140px]`.

- [ ] **Step 5: Add `Version` footer display**

`Version.tsx` renders:

```tsx
export function Version() {
  return <span className="text-xs text-text-secondary">v0.1.0</span>;
}
```

Use it in sidebar bottom.

- [ ] **Step 6: Verify mobile widths manually**

Run:

```powershell
npm run dev
```

Open dev tools widths:

- 375px.
- 768px.
- 1280px.

Expected:

- No incoherent overlap.
- Sidebar overlays on mobile.
- Timeline remains usable.
- Drawer fills mobile viewport.
- Cards collapse cleanly.

- [ ] **Step 7: Build**

Run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 13: Final Verification

**Files:**
- Modify only files required by failed checks.

- [ ] **Step 1: Run full tests**

Run:

```powershell
npm run test
```

Expected: all tests PASS.

- [ ] **Step 2: Run production build**

Run:

```powershell
npm run build
```

Expected: build completes successfully.

- [ ] **Step 3: Run local dev server**

Run:

```powershell
npm run dev
```

Expected: Vite prints a local URL such as `http://127.0.0.1:5173/`.

- [ ] **Step 4: Manual route walkthrough**

Open the dev URL and verify:

- `/` redirects to `/projects`.
- `/projects` can create and delete a project.
- `/analyze` accepts a video file and rejects text files.
- Analysis progress completes and shows all tabs.
- `/migrate/proj-1` edits a segment and repair clears gaps.
- `/result/proj-1` switches versions and opens export dialog.
- `/migrate/missing` shows project-not-found state.

- [ ] **Step 5: Manual responsive walkthrough**

At widths 375px, 768px, and 1280px, verify:

- Sidebar behavior is correct.
- Text fits buttons and cards.
- No charts overflow.
- Timeline remains navigable.
- Modal and drawer controls remain reachable.

- [ ] **Step 6: Commit if git exists**

Run:

```powershell
git status --short
```

Expected: if the command reports a repository, commit with:

```powershell
git add .
git commit -m "feat: build structforge mock mvp"
```

If `git status` reports "not a git repository", document that final work was not committed.

---

## Self-Review

Spec coverage:

- Four routes are covered in Tasks 5 through 11.
- Product-list foundation is covered in Task 6.
- Global store and mock data are covered in Tasks 2 and 3.
- Upload, progress, tabs, and charts are covered in Tasks 7 and 8.
- Migration editor, asset panel, drawer, history, and gap repair are covered in Tasks 9 and 10.
- Result preview, versions, timeline, radar, and export are covered in Task 11.
- Error, loading, empty, responsive, and accessibility states are covered in Tasks 4, 5, and 12.
- Verification is covered in Task 13.

Type consistency:

- All tasks use `VideoStructure`, `ScriptSegment`, `Asset`, `MaterialGap`, and `ResultVersion` from `src/shared/types.ts`.
- Store action names match every task that consumes them.
- Stable mock IDs match cross-page references.

Execution note:

- The workspace was not a git repository when planning began. Commit steps are included and are conditional on `git status` reporting a repository.
