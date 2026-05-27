import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ResultPage from './ResultPage';
import type { FinalScript } from '../shared/types';
import { useAppStore } from '../store';

const project = { id: 'proj-1', name: 'Headphones', description: '', status: 'editing', updatedAt: '2026-05-23T00:00:00Z' };
const finalScript: FinalScript = {
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
      source: 'packaging',
    },
  ],
  metadata: { warnings: [] },
};
const evaluatedVersions = {
  evaluationLabel: '\u7ed3\u6784\u89c4\u5219\u8bc4\u4f30',
  baseline: {
    id: 'original',
    name: '\u6837\u4f8b\u57fa\u7ebf',
    score: 66,
    metrics: {
      scoreDelta: 0,
      materialCoverage: { before: '100%', after: '100%', delta: '0%', positive: true },
      productExposure: { before: '8.0s', after: '8.0s', delta: '0.0s', positive: true },
      gapCount: { before: '0', after: '0', delta: '0', positive: true },
      ctaDuration: { before: '11.0s', after: '11.0s', delta: '0.0s', positive: true },
    },
    health: { hook_strength: 80, product_exposure_timing: 50, selling_point_proof: 50, pacing_compactness: 70, cta_persuasiveness: 80, overall: 66 },
    timeline: [{ id: 'seg-1', label: 'Hook', start: 0, end: 3, source: 'original' }],
  },
  versions: [
    {
      id: 'high_click',
      name: '\u9ad8\u70b9\u51fb\u7248',
      score: 71,
      metrics: {
        scoreDelta: 5,
        materialCoverage: { before: '100%', after: '100%', delta: '+0%', positive: true },
        productExposure: { before: '8.0s', after: '7.0s', delta: '-1.0s', positive: true },
        gapCount: { before: '0', after: '0', delta: '0', positive: true },
        ctaDuration: { before: '11.0s', after: '11.0s', delta: '+0.0s', positive: true },
      },
      health: { hook_strength: 100, product_exposure_timing: 55, selling_point_proof: 50, pacing_compactness: 70, cta_persuasiveness: 80, overall: 71 },
      timeline: [{ id: 'seg-1', label: 'Generated hook', start: 0, end: 3, source: 'packaging' }],
    },
  ],
};
const baselineOnlyVersions = {
  ...evaluatedVersions,
  versions: [],
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

  it('loads only rule-evaluated generated versions from the API', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(evaluatedVersions), {
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

    renderRoute('/result/proj-1');

    expect(await screen.findByText(/\u7ed3\u6784\u89c4\u5219\u8bc4\u4f30/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /\u9ad8\u70b9\u51fb\u7248/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Strong Hook/ })).not.toBeInTheDocument();
  });

  it('shows a baseline result without requesting a final script that does not exist yet', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(baselineOnlyVersions), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    useAppStore.setState({ currentScript: finalScript });

    renderRoute('/result/proj-1');

    expect(await screen.findByText(/\u5c1a\u672a\u751f\u6210\u65b0\u811a\u672c/)).toBeInTheDocument();
    const requestedUrls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
    expect(requestedUrls).toContain('http://127.0.0.1:8000/api/v1/migrate/proj-1/versions');
    expect(requestedUrls).not.toContain('http://127.0.0.1:8000/api/v1/migrate/proj-1');
  });

  it('switches evaluated result versions', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(evaluatedVersions), {
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
    await user.click(await screen.findByRole('button', { name: /\u9ad8\u70b9\u51fb\u7248/ }));
    expect(screen.getByText(/\+5/)).toBeInTheDocument();
    expect(screen.getByText(/8\.0s.*7\.0s/)).toBeInTheDocument();
  });

  it('formats negative structure score changes without a misleading plus prefix', async () => {
    const decreasedVersions = {
      ...evaluatedVersions,
      versions: [{ ...evaluatedVersions.versions[0], score: 62, metrics: { ...evaluatedVersions.versions[0].metrics, scoreDelta: -4 } }],
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([project]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(decreasedVersions), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(finalScript), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup();

    renderRoute('/result/proj-1');
    await user.click(await screen.findByRole('button', { name: /\u9ad8\u70b9\u51fb\u7248/ }));

    expect(screen.getByText('-4')).toBeInTheDocument();
    expect(screen.queryByText('+-4')).not.toBeInTheDocument();
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
        new Response(JSON.stringify(evaluatedVersions), {
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

  it('shows service-derived source for generated timeline segments', async () => {
    const recomposedScript = {
      ...finalScript,
      segments: [{ ...finalScript.segments[0], asset_id: 'asset-video', source: 'recompose' }],
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...evaluatedVersions,
            versions: [
              {
                ...evaluatedVersions.versions[0],
                timeline: [{ id: 'seg-1', label: 'Generated hook', start: 0, end: 3, source: 'recompose' }],
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      );
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(recomposedScript), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    renderRoute('/result/proj-1');

    expect((await screen.findAllByText('\u7d20\u6750\u91cd\u7ec4')).length).toBeGreaterThan(0);
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
        new Response(JSON.stringify(evaluatedVersions), {
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

  it('offers only implemented script exports and downloads them locally', async () => {
    const createObjectURL = vi.fn(() => 'blob:script');
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([project]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(evaluatedVersions), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(finalScript), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup();

    renderRoute('/result/proj-1');
    await user.click(await screen.findByRole('button', { name: /\u5bfc\u51fa\u89c6\u9891/ }));

    expect(screen.queryByText(/PDF/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /\u4e0b\u8f7d\u811a\u672c JSON/ }));
    await user.click(screen.getByRole('button', { name: /\u4e0b\u8f7d\u5b57\u5e55 SRT/ }));
    expect(createObjectURL).toHaveBeenCalledTimes(2);
  });
});
