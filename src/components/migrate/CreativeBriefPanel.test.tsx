import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CreativeBriefPanel } from './CreativeBriefPanel';

describe('CreativeBriefPanel', () => {
  it('saves product name and selling points', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<CreativeBriefPanel brief={undefined} projectId="test-proj" onSave={onSave} />);

    await user.type(screen.getByPlaceholderText(/产品名称/), 'Quiet Pro');
    await user.type(screen.getByPlaceholderText(/核心卖点/), '主动降噪\n轻盈佩戴');
    await user.click(screen.getByRole('button', { name: /保存/ }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      productName: 'Quiet Pro',
      sellingPoints: ['主动降噪', '轻盈佩戴'],
    }));
  });
});
