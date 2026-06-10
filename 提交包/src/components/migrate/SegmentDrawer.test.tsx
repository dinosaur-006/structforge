import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SegmentDrawer } from './SegmentDrawer';
import { mockAnalysisResult } from '../../mocks/analysisResult';

describe('SegmentDrawer', () => {
  it('does not promise unsupported BGM beat alignment', () => {
    render(
      <SegmentDrawer
        open
        segment={mockAnalysisResult.script[0]}
        assets={[]}
        onClose={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    expect(screen.queryByText(/BGM/)).not.toBeInTheDocument();
  });
});
