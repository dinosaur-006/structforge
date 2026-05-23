import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ResultPage from './ResultPage';
import { useAppStore } from '../store';

const project = { id: 'proj-1', name: 'Headphones', description: '', status: 'editing', updatedAt: '2026-05-23T00:00:00Z' };
const finalScript = {
  version: 'high_click',
  total_duration: 35,
  segments: [
    {
      id: 'seg-1',
      type: 'hook',
      start: 0,
      end: 3,
      duration: 3,
      script: 'Generated hook',
      visual: 'Product close-up',
      asset_id: null,
      subtitle_style: 'clean_caption',
      transition: 'hard_cut',
      locked: false,
    },
  ],
  metadata: { warnings: [] },
};

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
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    useAppStore.getState().resetForTest();
  });

  afterEach(() => vi.unstubAllGlobals());

  it('switches result versions', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Final script not found' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    const user = userEvent.setup();
    renderRoute('/result/proj-1');
    await user.click(await screen.findByRole('button', { name: /Strong Hook/ }));
    expect(screen.getByText(/\+29/)).toBeInTheDocument();
  });

  it('renders generated final script timeline when one is available', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(finalScript), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    renderRoute('/result/proj-1');

    expect(await screen.findByText('Generated hook')).toBeInTheDocument();
  });

  it('starts a render job from the export dialog and passes the output to the player', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(finalScript), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ job_id: 'render-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'completed', progress: 100, output_url: '/outputs/proj-1/original.mp4', warnings: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    const user = userEvent.setup();

    renderRoute('/result/proj-1');
    await user.click(await screen.findByRole('button', { name: /\u5bfc\u51fa\u89c6\u9891/ }));
    await user.click(screen.getByRole('button', { name: /\u5f00\u59cb\u5bfc\u51fa/ }));

    expect(await screen.findByTestId('rendered-video')).toHaveAttribute('src', 'http://127.0.0.1:8000/outputs/proj-1/original.mp4');
    expect(screen.getByRole('link', { name: /\u4e0b\u8f7d\u89c6\u9891/ })).toHaveAttribute('href', 'http://127.0.0.1:8000/outputs/proj-1/original.mp4');
  });
});
