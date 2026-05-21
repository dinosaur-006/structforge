import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import ResultPage from './ResultPage';
import { useAppStore } from '../store';

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/result/:projectId" element={<ResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ResultPage', () => {
  beforeEach(() => useAppStore.getState().resetForTest());

  it('switches result versions', async () => {
    const user = userEvent.setup();
    renderRoute('/result/proj-1');
    await user.click(screen.getByRole('button', { name: /Strong Hook/ }));
    expect(screen.getByText(/\+29/)).toBeInTheDocument();
  });
});
