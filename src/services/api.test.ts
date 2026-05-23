import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends json requests and parses json responses', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 'proj-1', name: 'Launch', description: '', status: 'draft', updatedAt: '2026-05-23T00:00:00Z' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const project = await api.createProject({ name: 'Launch', description: '' });

    expect(project.id).toBe('proj-1');
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/projects',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Launch', description: '' }),
      }),
    );
  });

  it('does not set json content type for form data uploads', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: 'job-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.startAnalysis(new File(['video'], 'sample.mp4', { type: 'video/mp4' }), 'proj-1');

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.method).toBe('POST');
    expect(init?.headers).toBeUndefined();
    expect(init?.body).toBeInstanceOf(FormData);
  });

  it('uploads assets as form data without forcing json content type', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ asset_id: 'asset-1', analysis: { description: '产品特写' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.analyzeAsset('proj-1', new File(['copy'], 'offer.txt', { type: 'text/plain' }));

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe('http://127.0.0.1:8000/api/v1/assets/analyze/proj-1');
    expect(init?.method).toBe('POST');
    expect(init?.headers).toBeUndefined();
    expect(init?.body).toBeInstanceOf(FormData);
  });

  it('calls gap detection and fix endpoints', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ gaps: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ fixed_count: 0, details: [], gaps: [], assets: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    await api.listGaps('proj-1');
    await api.fixAllGaps('proj-1');

    expect(fetch).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8000/api/v1/gaps/proj-1', {});
    expect(fetch).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/api/v1/gaps/proj-1/fix-all', { method: 'POST' });
  });

  it('calls migrate script endpoints with json bodies', async () => {
    const script = { version: 'high_click', total_duration: 35, segments: [], metadata: { warnings: [] } };
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(script), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...script, version: 'high_quality' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(script), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await api.migrateScript('proj-1', 'high_click');
    await api.migrateVariant('proj-1', 'high_quality');
    await api.getFinalScript('proj-1');

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:8000/api/v1/migrate/proj-1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ style: 'high_click' }) }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:8000/api/v1/migrate/proj-1/variant',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ style: 'high_quality' }) }),
    );
    expect(fetch).toHaveBeenNthCalledWith(3, 'http://127.0.0.1:8000/api/v1/migrate/proj-1', {});
  });

  it('calls render endpoints with version and resolution', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ job_id: 'render-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'completed', progress: 100, output_url: '/outputs/proj-1/strong_hook.mp4', warnings: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    await api.startRender('proj-1', 'strong_hook', '1080p');
    await api.getRenderJob('render-1');

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:8000/api/v1/render/proj-1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ version: 'strong_hook', resolution: '1080p' }) }),
    );
    expect(fetch).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/api/v1/render/render-1', {});
  });

  it('throws readable FastAPI errors', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Project not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(api.getProject('missing')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Project not found',
      status: 404,
    } satisfies Partial<ApiError>);
  });
});
