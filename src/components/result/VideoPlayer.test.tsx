import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { VideoPlayer } from './VideoPlayer';

const timeline = [{ id: 'seg-1', label: 'Hook', start: 0, end: 3, source: 'original' as const }];

describe('VideoPlayer', () => {
  it('renders a real video element when output src is available', () => {
    render(<VideoPlayer timeline={timeline} src="http://127.0.0.1:8000/outputs/proj-1/original.mp4" />);

    expect(screen.getByTestId('rendered-video')).toHaveAttribute('src', 'http://127.0.0.1:8000/outputs/proj-1/original.mp4');
  });

  it('keeps the placeholder player when no src is available', () => {
    render(<VideoPlayer timeline={timeline} />);

    expect(screen.getByRole('button', { name: 'Volume' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
  });

  it('shows blueprint indicator when timeline has draft segments', () => {
    const draftTimeline = [{ id: 'seg-1', label: 'Hook', start: 0, end: 3, source: 'aigc_draft' as const }];
    render(<VideoPlayer timeline={draftTimeline} hasDraftSegments />);

    expect(screen.getByText(/AI 蓝图预留位/)).toBeInTheDocument();
  });
});
