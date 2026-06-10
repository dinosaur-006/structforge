import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalysisProgress } from './AnalysisProgress';

describe('AnalysisProgress', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows an active elapsed waiting state before real progress is reported', () => {
    vi.useFakeTimers();
    render(<AnalysisProgress progress={0} stage="正在抽帧..." />);

    const progressbar = screen.getByRole('progressbar', { name: '视频分析进度' });
    expect(screen.getByText('处理中')).toBeInTheDocument();
    expect(screen.getByText('已用时 00:00')).toBeInTheDocument();
    expect(progressbar).not.toHaveAttribute('aria-valuenow');

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByText('已用时 00:03')).toBeInTheDocument();
    expect(progressbar).toHaveAttribute('aria-valuetext', '正在处理中，已用时 00:03');
  });

  it('shows only the real completion percentage once it is available', () => {
    render(<AnalysisProgress progress={42} stage="正在识别关键帧..." />);

    const progressbar = screen.getByRole('progressbar', { name: '视频分析进度' });
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.queryByText('处理中')).not.toBeInTheDocument();
    expect(progressbar).toHaveAttribute('aria-valuenow', '42');
  });
});
