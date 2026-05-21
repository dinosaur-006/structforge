import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AppLayout } from './AppLayout';

describe('AppLayout', () => {
  it('renders navigation and child content', () => {
    render(
      <MemoryRouter initialEntries={['/projects']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/projects" element={<div>Projects body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('StructForge')).toBeInTheDocument();
    expect(screen.getByText('Projects body')).toBeInTheDocument();
  });
});
