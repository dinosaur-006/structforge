import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import ProjectListPage from './ProjectListPage';
import { useAppStore } from '../store';

describe('ProjectListPage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('creates a project from the dialog', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ProjectListPage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: /\u65b0\u5efa\u9879\u76ee/ }));
    await user.type(screen.getByLabelText(/\u9879\u76ee\u540d\u79f0/), 'New Clip');
    await user.click(screen.getByRole('button', { name: /\u521b\u5efa/ }));
    expect(screen.getByText('New Clip')).toBeInTheDocument();
  });
});
