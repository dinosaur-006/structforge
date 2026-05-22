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
          JSON.stringify({ id: 'proj-new', name: 'New Clip', description: '', status: 'draft', updatedAt: '2026-05-23T00:00:00Z' }),
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
    await user.click(screen.getByRole('button', { name: /\u521b\u5efa/ }));
    expect(screen.getByText('New Clip')).toBeInTheDocument();
  });
});
