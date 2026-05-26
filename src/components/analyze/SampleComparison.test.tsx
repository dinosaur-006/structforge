import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SampleComparison } from './SampleComparison';
import { mockAnalysisResult } from '../../mocks/analysisResult';

describe('SampleComparison', () => {
  it('compares analyzed samples and allows choosing the reference', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SampleComparison
        samples={[
          { job_id: 'job-1', status: 'completed', progress: 100, stage: 'Done', result: mockAnalysisResult, isReference: true },
          { job_id: 'job-2', status: 'completed', progress: 100, stage: 'Done', result: { ...mockAnalysisResult, meta: { ...mockAnalysisResult.meta, shots: 18 } }, isReference: false },
        ]}
        onSelect={onSelect}
      />,
    );

    expect(screen.getByText('结构对比')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '选择为结构模板' }));
    expect(onSelect).toHaveBeenCalledWith('job-2');
  });
});
