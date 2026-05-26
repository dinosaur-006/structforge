import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ProjectListPage from './ProjectListPage';
import { useAppStore } from '../store';

describe('ProjectListPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    useAppStore.getState().resetForTest();
  });

  afterEach(() => vi.unstubAllGlobals());

  it('creates a project from the dialog', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 'proj-new',
            name: 'New Clip',
            description: '',
            brief: { productName: 'Quiet Pro', sellingPoints: ['主动降噪'], targetAudience: '通勤人士', offer: '首发 299 元', tone: '专业', mandatoryClaims: [] },
            status: 'draft',
            updatedAt: '2026-05-23T00:00:00Z',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ProjectListPage />
      </MemoryRouter>,
    );
    await user.click(screen.getAllByRole('button', { name: /\u65b0\u5efa\u9879\u76ee/ })[0]);
    await user.type(screen.getByLabelText(/\u9879\u76ee\u540d\u79f0/), 'New Clip');
    await user.type(screen.getByLabelText(/商品名称/), 'Quiet Pro');
    await user.type(screen.getByLabelText(/核心卖点/), '主动降噪');
    await user.type(screen.getByLabelText(/目标人群/), '通勤人士');
    await user.type(screen.getByLabelText(/优惠信息/), '首发 299 元');
    await user.type(screen.getByLabelText(/表达语气/), '专业');
    await user.click(screen.getByRole('button', { name: /\u521b\u5efa/ }));
    expect(screen.getByText('New Clip')).toBeInTheDocument();
    expect(fetch).toHaveBeenLastCalledWith(
      'http://127.0.0.1:8000/api/v1/projects',
      expect.objectContaining({ body: expect.stringContaining('"productName":"Quiet Pro"') }),
    );
  });
});
