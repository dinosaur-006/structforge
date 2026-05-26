import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { GapPanel } from './GapPanel';
import type { MaterialGap } from '../../shared/types';

const gap: MaterialGap = {
  id: 'gap-seg-1',
  segmentId: 'seg-1',
  severity: 'critical',
  description: 'Hook 素材缺口',
  requiredSlot: '0-3s Hook 画面',
  selectedStrategyId: 'packaging',
  recommendedStrategy: 'packaging',
  status: 'open',
  strategies: [
    { id: 'packaging', name: '包装补全', description: '生成包装图', available: true },
    { id: 'aigc', name: 'AIGC 生成', description: '生成背景图', available: false, unavailableReason: '需配置即梦 API' },
  ],
};

describe('GapPanel', () => {
  it('renders real gaps and applies the selected strategy', async () => {
    const onFixGap = vi.fn();
    const user = userEvent.setup();
    render(<GapPanel gaps={[gap]} isFixing={false} onFixAll={vi.fn()} onFixGap={onFixGap} />);

    expect(screen.getByText('Hook 素材缺口')).toBeInTheDocument();
    await user.click(screen.getByLabelText('包装补全'));
    await user.click(screen.getByRole('button', { name: '应用选中策略' }));

    expect(screen.getByLabelText('AIGC 生成')).toBeDisabled();
    expect(screen.getByText('需配置即梦 API')).toBeInTheDocument();
    expect(onFixGap).toHaveBeenCalledWith('gap-seg-1', 'packaging');
  });
});
