import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MigratePage from './MigratePage';
import { useAppStore } from '../store';
import { mockAnalysisResult } from '../mocks/analysisResult';

const project = { id: 'proj-1', name: 'Headphones', description: '', status: 'editing', updatedAt: '2026-05-23T00:00:00Z' };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/migrate/:projectId" element={<MigratePage />} />
        <Route path="/analyze" element={<div>Analyze target</div>} />
        <Route path="/result/:projectId" element={<div>Result target</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const finalScript = {
  version: 'fast_pace',
  total_duration: 35,
  segments: [],
  metadata: { warnings: [] },
};

describe('MigratePage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    useAppStore.getState().resetForTest();
  });

  afterEach(() => vi.unstubAllGlobals());

  it('shows missing project state', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Project has no structure' }, 404));
    renderRoute('/migrate/missing');
    expect(await screen.findByText(/\u9879\u76ee\u4e0d\u5b58\u5728/)).toBeInTheDocument();
  });

  it('redirects draft projects to analysis without requesting structure', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse([{ id: 'proj-draft', name: 'Draft', description: '', status: 'draft', updatedAt: '2026-05-23T00:00:00Z' }]),
    );

    renderRoute('/migrate/proj-draft');

    expect(await screen.findByText('Analyze target')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('edits a segment through the drawer', async () => {
    const edited = {
      ...mockAnalysisResult,
      script: mockAnalysisResult.script.map((segment, index) => (index === 0 ? { ...segment, duration: 4, end: 4 } : segment)),
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(mockAnalysisResult))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
      .mockResolvedValueOnce(jsonResponse(edited))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }));
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');
    await user.click(await screen.findByRole('button', { name: /Hook/ }));
    await user.clear(screen.getByLabelText(/\u65f6\u957f/));
    await user.type(screen.getByLabelText(/\u65f6\u957f/), '4');
    await user.click(screen.getByRole('button', { name: /\u5e94\u7528\u66f4\u6539/ }));
    expect(await screen.findByText('4s')).toBeInTheDocument();
  });

  it('generates a script with the selected style before navigating to results', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(mockAnalysisResult))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
      .mockResolvedValueOnce(jsonResponse(finalScript));
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');

    await user.click(await screen.findByRole('button', { name: /\u751f\u6210\u89c6\u9891/ }));

    expect(fetch).toHaveBeenLastCalledWith(
      'http://127.0.0.1:8000/api/v1/migrate/proj-1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ style: 'fast_pace' }) }),
    );
    expect(await screen.findByText('Result target')).toBeInTheDocument();
  });
});
