import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MigratePage from './MigratePage';
import { useAppStore } from '../store';
import { mockAnalysisResult } from '../mocks/analysisResult';

const project = { id: 'proj-1', name: 'Headphones', description: '', status: 'editing', updatedAt: '2026-05-23T00:00:00Z', brief: { productName: 'Headphones', sellingPoints: ['Noise cancellation'], targetAudience: '', offer: '', tone: '', mandatoryClaims: [] } };

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
  version: 'default',
  total_duration: 35,
  segments: [],
  metadata: { warnings: [] },
};

/** Mock chain: projects → structure → assets → gaps → fixAll */
function mockLoadAndFix() {
  vi.mocked(fetch)
    .mockResolvedValueOnce(jsonResponse([project]))
    .mockResolvedValueOnce(jsonResponse(mockAnalysisResult))
    .mockResolvedValueOnce(jsonResponse([]))
    .mockResolvedValueOnce(jsonResponse({ gaps: [] }))
    .mockResolvedValueOnce(jsonResponse({ fixed_count: 0, gaps: [], assets: [], updated_structure: mockAnalysisResult }));
}

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
    expect(await screen.findByText(/项目不存在/)).toBeInTheDocument();
  });

  it('redirects draft projects to analysis', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([
      { id: 'proj-draft', name: 'Draft', description: '', status: 'draft', updatedAt: '2026-05-23T00:00:00Z' },
    ]));
    renderRoute('/migrate/proj-draft');
    expect(await screen.findByText('Analyze target')).toBeInTheDocument();
  });

  it('generates a script and navigates to result', async () => {
    mockLoadAndFix();
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(finalScript));
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');

    await user.click(await screen.findByRole('button', { name: /生成视频/ }));
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/migrate/proj-1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ style: 'default' }) }),
    );
    expect(await screen.findByText('Result target')).toBeInTheDocument();
  });

  it('generates high-click style script', async () => {
    mockLoadAndFix();
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ...finalScript, version: 'high_click' }));
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');

    await user.selectOptions(await screen.findByRole('combobox', { name: /风格/ }), 'click');
    await user.click(screen.getByRole('button', { name: /生成视频/ }));

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/migrate/proj-1',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ style: 'high_click' }) }),
    );
  });
});
