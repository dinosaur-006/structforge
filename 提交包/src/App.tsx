import { useCallback } from 'react';
import { RouterProvider } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LLMOutagePanel } from './components/shared/LLMOutagePanel';
import { Toast } from './components/ui/Toast';
import { router } from './router';
import { useAppStore } from './store';

function LLMOutageOverlay() {
  const outage = useAppStore((s) => s.llmOutage);
  const setLLMOutage = useAppStore((s) => s.setLLMOutage);

  const handleRetry = useCallback(() => {
    setLLMOutage(null);
    // Trigger a page reload to retry the failed operation
    window.location.reload();
  }, [setLLMOutage]);

  const handleOffline = useCallback(() => {
    setLLMOutage(null);
    // Allow user to continue with rule-engine fallback
    // The existing fallback paths (build_local_structure_payload etc.) remain
    // available as explicit opt-in, not silent degradation
  }, [setLLMOutage]);

  if (!outage) return null;

  return (
    <LLMOutagePanel
      operation={outage.operation}
      error={outage.error}
      suggestion={outage.suggestion}
      retryable={outage.retryable}
      onRetry={handleRetry}
      onWorkOffline={handleOffline}
      onDismiss={() => setLLMOutage(null)}
    />
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
      <Toast />
      <LLMOutageOverlay />
    </ErrorBoundary>
  );
}
