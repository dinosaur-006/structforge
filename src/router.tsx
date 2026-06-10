import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';

const ProjectListPage = lazy(() => import('./pages/ProjectListPage'));
const AnalyzePage = lazy(() => import('./pages/AnalyzePage'));
const MigratePage = lazy(() => import('./pages/MigratePage'));
const ResultPage = lazy(() => import('./pages/ResultPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <Navigate to="/projects" replace /> },
      { path: '/projects', element: <ProjectListPage /> },
      { path: '/analyze', element: <AnalyzePage /> },
      { path: '/migrate/:projectId', element: <MigratePage /> },
      { path: '/result/:projectId', element: <ResultPage /> },
      { path: '/history', element: <HistoryPage /> },
      { path: '/settings', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
