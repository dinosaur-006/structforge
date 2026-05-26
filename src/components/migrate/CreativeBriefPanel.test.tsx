import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CreativeBriefPanel } from './CreativeBriefPanel';

describe('CreativeBriefPanel', () => {
  it('submits structured product information for script generation', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<CreativeBriefPanel brief={undefined} onSave={onSave} />);

    await user.type(screen.getByLabelText(/商品名称/), 'Quiet Pro');
    await user.type(screen.getByLabelText(/核心卖点/), '主动降噪\n轻盈佩戴');
    await user.type(screen.getByLabelText(/目标人群/), '通勤人士');
    await user.type(screen.getByLabelText(/优惠信息/), '首发 299 元');
    await user.click(screen.getByRole('button', { name: /保存简报/ }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      productName: 'Quiet Pro',
      sellingPoints: ['主动降噪', '轻盈佩戴'],
      targetAudience: '通勤人士',
      offer: '首发 299 元',
    }));
  });
});
