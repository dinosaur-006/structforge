import { MemoryRouter } from 'react-router-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AnalyzePage from './AnalyzePage';
import { useAppStore } from '../store';

describe('AnalyzePage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

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
    render(
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>,
    );
    const input = screen.getByLabelText(/\u9009\u62e9\u89c6\u9891/);
    fireEvent.change(input, { target: { files: [new File(['video'], 'sample.mp4', { type: 'video/mp4' })] } });
    fireEvent.click(screen.getByRole('button', { name: /\u5f00\u59cb\u5206\u6790/ }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6500);
    });
    expect(screen.getByText(/\u811a\u672c\u7ed3\u6784/)).toBeInTheDocument();
    vi.useRealTimers();
  });
});
