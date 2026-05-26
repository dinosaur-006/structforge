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

const capabilities = {
  llm: { state: 'configured', label: 'Doubao LLM', detail: '已提供 LLM 配置；首次真实生成时验证授权可用性' },
  vision: { state: 'fallback', label: 'Vision', detail: '使用占位画面描述' },
  asr: { state: 'disabled', label: 'ASR', detail: '未启用语音转写' },
  aigc: { state: 'disabled', label: 'AIGC', detail: '未配置生成图片' },
  taskExecution: { state: 'inline', label: 'Tasks', detail: '本地同步任务模式' },
};

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
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(capabilities));
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

  it('accepts up to three sample videos in one selection', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(capabilities));
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);

    expect(input).toHaveAttribute('multiple');
    fireEvent.change(input, {
      target: {
        files: [
          new File(['first'], 'first.mp4', { type: 'video/mp4' }),
          new File(['second'], 'second.mp4', { type: 'video/mp4' }),
        ],
      },
    });

    expect(screen.getByText(/\u5df2\u9009\u62e9\uff1a2 \u6761\u6837\u4f8b\u89c6\u9891/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /\u5206\u6790 2 \u6761\u6837\u4f8b/ })).toBeInTheDocument();
  });

  it('runs mock analysis', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(capabilities))
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

  it('shows whether model-backed capabilities are real or in fallback mode', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(capabilities));
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Doubao LLM')).toBeInTheDocument();
    expect(screen.getByText('仅显示配置状态，真实可用性以执行结果为准')).toBeInTheDocument();
    expect(screen.getByText('已提供 LLM 配置；首次真实生成时验证授权可用性')).toBeInTheDocument();
    expect(screen.getByText('使用占位画面描述')).toBeInTheDocument();
  });
});
