import { CheckCircle2, Info, RefreshCcw, XCircle } from 'lucide-react';
import { useAppStore } from '../../store';

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

export function Toast() {
  const toasts = useAppStore((state) => state.toasts);
  const removeToast = useAppStore((state) => state.removeToast);
  const retryLastAction = useAppStore((state) => state.retryLastAction);

  return (
    <div className="fixed right-4 top-4 z-[60] flex w-[min(360px,calc(100vw-32px))] flex-col gap-3" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.tone];
        return (
          <div
            key={toast.id}
            role="alert"
            className="rounded-xl border border-border bg-card/95 p-4 text-left shadow-md backdrop-blur transition-colors hover:border-primary/40"
          >
            <button
              type="button"
              className="flex w-full gap-3"
              onClick={() => removeToast(toast.id)}
            >
              <Icon className="h-5 w-5 flex-none text-primary" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-text-primary">{toast.title}</p>
                {toast.description ? <p className="mt-1 text-sm text-text-secondary">{toast.description}</p> : null}
              </div>
            </button>
            {toast.tone === 'error' ? (
              <button
                type="button"
                className="mt-3 flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-primary hover:bg-sidebar transition-colors"
                onClick={() => { removeToast(toast.id); void retryLastAction(); }}
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                重试
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
