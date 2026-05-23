import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from './index';
import { mockAnalysisResult } from '../mocks/analysisResult';

const project = {
  id: 'proj-1',
  name: 'Launch Clip',
  description: 'Draft',
  status: 'draft' as const,
  updatedAt: '2026-05-23T00:00:00Z',
};

const textAsset = {
  id: 'asset-text',
  name: 'offer.txt',
  type: 'text' as const,
  tag: '优惠购买',
  matchStatus: 'matched' as const,
  matchScore: 91,
  color: '#5C8B67',
};

const openGap = {
  id: 'gap-seg-1',
  segmentId: 'seg-1',
  severity: 'critical' as const,
  description: 'Hook 素材缺口',
  requiredSlot: '0-3s Hook 画面',
  selectedStrategyId: 'packaging',
  recommendedStrategy: 'packaging',
  status: 'open' as const,
  strategies: [{ id: 'packaging', name: '包装补全', description: '生成包装图' }],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('app store', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    useAppStore.getState().resetForTest();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('creates and removes projects through the API', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const id = await useAppStore.getState().addProject('Launch Clip', 'Draft');
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(true);
    await useAppStore.getState().removeProject(id);
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(false);
    expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/projects', expect.objectContaining({ method: 'POST' }));
  });

  it('loads structure, updates a segment, and supports undo redo through the API', async () => {
    const edited = {
      ...mockAnalysisResult,
      script: mockAnalysisResult.script.map((segment, index) => (index === 0 ? { ...segment, duration: 4, end: 4 } : segment)),
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(mockAnalysisResult))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
      .mockResolvedValueOnce(jsonResponse(edited))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
      .mockResolvedValueOnce(jsonResponse({ action: 'undo', available: true, structure: mockAnalysisResult }))
      .mockResolvedValueOnce(jsonResponse({ action: 'redo', available: true, structure: edited }));

    await useAppStore.getState().loadProjectStructure('proj-1');
    await useAppStore.getState().updateSegment('seg-hook', { duration: 4, end: 4 });
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
    await useAppStore.getState().undo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(3);
    await useAppStore.getState().redo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
  });

  it('keeps current structure when undo is unavailable', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(mockAnalysisResult))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
      .mockResolvedValueOnce(jsonResponse({ action: 'undo', available: false, structure: mockAnalysisResult }));

    await useAppStore.getState().loadProjectStructure('proj-1');
    await useAppStore.getState().undo();

    expect(useAppStore.getState().currentStructure?.meta.duration).toBe(mockAnalysisResult.meta.duration);
    expect(useAppStore.getState().toasts.at(-1)?.tone).toBe('info');
  });

  it('uploads an asset, refreshes matching, and stores returned assets', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ asset_id: 'asset-text', analysis: { description: '优惠购买' } }))
      .mockResolvedValueOnce(jsonResponse({ matches: [{ asset_id: 'asset-text', segment_id: 'seg-3', score: 91, status: 'matched' }] }))
      .mockResolvedValueOnce(jsonResponse([textAsset]))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }));

    useAppStore.setState({ activeProjectId: 'proj-1' });
    await useAppStore.getState().uploadAsset(new File(['优惠购买'], 'offer.txt', { type: 'text/plain' }));

    expect(useAppStore.getState().assets).toEqual([textAsset]);
    expect(useAppStore.getState().assetLoading).toBe(false);
  });

  it('fetches gaps and fixes all gaps through the API', async () => {
    const fixedStructure = {
      ...mockAnalysisResult,
      script: mockAnalysisResult.script.map((segment, index) => (index === 0 ? { ...segment, assetId: 'asset-fill' } : segment)),
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ gaps: [openGap] }))
      .mockResolvedValueOnce(jsonResponse({ fixed_count: 1, details: [], gaps: [], updated_structure: fixedStructure, assets: [textAsset] }));

    useAppStore.setState({ activeProjectId: 'proj-1', currentStructure: mockAnalysisResult });
    await useAppStore.getState().fetchGaps('proj-1');
    await useAppStore.getState().fixAllGaps();

    expect(useAppStore.getState().gaps).toEqual([]);
    expect(useAppStore.getState().assets).toEqual([textAsset]);
    expect(useAppStore.getState().currentStructure?.script[0].assetId).toBe('asset-fill');
  });

  it('reports asset upload errors and clears loading state', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Upload failed'));

    useAppStore.setState({ activeProjectId: 'proj-1' });
    await useAppStore.getState().uploadAsset(new File(['bad'], 'bad.txt', { type: 'text/plain' }));

    expect(useAppStore.getState().assetLoading).toBe(false);
    expect(useAppStore.getState().toasts.at(-1)).toMatchObject({ tone: 'error' });
  });

  it('uploads video and polls analysis until completion', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-1' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'processing', progress: 25, stage: 'Extracting' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'completed', progress: 100, stage: 'Done', result: mockAnalysisResult }))
      .mockResolvedValueOnce(jsonResponse([{ ...project, status: 'editing' }]));

    useAppStore.getState().setVideoFile(new File(['video'], 'sample.mp4', { type: 'video/mp4' }));
    const promise = useAppStore.getState().startAnalysis();
    await vi.advanceTimersByTimeAsync(1100);
    const projectId = await promise;

    expect(projectId).toBe('proj-1');
    expect(useAppStore.getState().analysisResult?.health.overall).toBe(mockAnalysisResult.health.overall);
    expect(useAppStore.getState().isAnalyzing).toBe(false);
  });

  it('stops polling and reports an error when analysis polling fails', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-1' }))
      .mockRejectedValueOnce(new Error('Network interrupted'));

    useAppStore.getState().setVideoFile(new File(['video'], 'sample.mp4', { type: 'video/mp4' }));
    const projectId = await useAppStore.getState().startAnalysis();

    expect(projectId).toBeUndefined();
    expect(useAppStore.getState().isAnalyzing).toBe(false);
    expect(useAppStore.getState().apiError).toBe('Network interrupted');
    expect(useAppStore.getState().toasts.at(-1)).toMatchObject({ tone: 'error', title: '分析失败' });
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
