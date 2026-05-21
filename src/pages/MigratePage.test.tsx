import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import MigratePage from './MigratePage';
import { useAppStore } from '../store';

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/migrate/:projectId" element={<MigratePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('MigratePage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('shows missing project state', () => {
    renderRoute('/migrate/missing');
    expect(screen.getByText(/\u9879\u76ee\u4e0d\u5b58\u5728/)).toBeInTheDocument();
  });

  it('edits a segment through the drawer', async () => {
    const user = userEvent.setup();
    renderRoute('/migrate/proj-1');
    await user.click(screen.getByRole('button', { name: /Hook/ }));
    await user.clear(screen.getByLabelText(/\u65f6\u957f/));
    await user.type(screen.getByLabelText(/\u65f6\u957f/), '4');
    await user.click(screen.getByRole('button', { name: /\u5e94\u7528\u66f4\u6539/ }));
    expect(screen.getByText('4s')).toBeInTheDocument();
  });
});
