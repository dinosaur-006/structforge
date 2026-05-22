import { MemoryRouter } from 'react-router-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AnalyzePage from './AnalyzePage';
import { useAppStore } from '../store';
import { mockAnalysisResult } from '../mocks/analysisResult';

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

describe('AnalyzePage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    useAppStore.getState().resetForTest();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('rejects non-video files', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);
    await user.upload(input, new File(['x'], 'notes.txt', { type: 'text/plain' }));
    expect(screen.getByText(/\u4ec5\u652f\u6301/)).toBeInTheDocument();
  });

  it('runs mock analysis', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ id: 'proj-1', name: 'sample', description: '', status: 'draft', updatedAt: '2026-05-23T00:00:00Z' }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-1' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'processing', progress: 40, stage: 'Processing' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'completed', progress: 100, stage: 'Done', result: mockAnalysisResult }))
      .mockResolvedValueOnce(jsonResponse([{ id: 'proj-1', name: 'sample', description: '', status: 'editing', updatedAt: '2026-05-23T00:00:00Z' }]));
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);
    fireEvent.change(input, { target: { files: [new File(['video'], 'sample.mp4', { type: 'video/mp4' })] } });
    fireEvent.click(screen.getByRole('button', { name: /\u5f00\u59cb\u5206\u6790/ }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1100);
      await Promise.resolve();
    });
    expect(screen.getByText(/\u811a\u672c\u7ed3\u6784/)).toBeInTheDocument();
  });
});
