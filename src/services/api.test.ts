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
