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
      </Routes>
    </MemoryRouter>,
  );
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
    expect(await screen.findByText(/\u9879\u76ee\u4e0d\u5b58\u5728/)).toBeInTheDocument();
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
      .mockResolvedValueOnce(jsonResponse(edited));
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');
    await user.click(await screen.findByRole('button', { name: /Hook/ }));
    await user.clear(screen.getByLabelText(/\u65f6\u957f/));
    await user.type(screen.getByLabelText(/\u65f6\u957f/), '4');
    await user.click(screen.getByRole('button', { name: /\u5e94\u7528\u66f4\u6539/ }));
    expect(await screen.findByText('4s')).toBeInTheDocument();
  });
});
