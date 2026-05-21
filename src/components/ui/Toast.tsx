import { CheckCircle2, Info, XCircle } from 'lucide-react';
import { useAppStore } from '../../store';

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

export function Toast() {
  const toasts = useAppStore((state) => state.toasts);
  const removeToast = useAppStore((state) => state.removeToast);

  return (
    <div className="fixed right-4 top-4 z-[60] flex w-[min(360px,calc(100vw-32px))] flex-col gap-3" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.tone];
        return (
          <button
            key={toast.id}
            type="button"
            className="rounded-lg border border-border bg-card/95 p-4 text-left shadow-md backdrop-blur transition-colors hover:border-primary/40"
            onClick={() => removeToast(toast.id)}
          >
            <div className="flex gap-3">
              <Icon className="h-5 w-5 flex-none text-primary" />
              <div>
                <p className="font-semibold text-text-primary">{toast.title}</p>
                {toast.description ? <p className="mt-1 text-sm text-text-secondary">{toast.description}</p> : null}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
