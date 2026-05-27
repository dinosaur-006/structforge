import { RouterProvider } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Toast } from './components/ui/Toast';
import { router } from './router';

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
      <Toast />
    </ErrorBoundary>
  );
}
