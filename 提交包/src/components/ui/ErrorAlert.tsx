import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

export interface ErrorAlertProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function ErrorAlert({ title, description, action }: ErrorAlertProps) {
  return (
    <div className="rounded-xl border border-error/30 bg-card p-5 text-error" role="alert">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-none" />
        <div>
          <h3 className="font-semibold text-text-primary">{title}</h3>
          {description ? <p className="mt-1 text-sm leading-6 text-text-secondary">{description}</p> : null}
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </div>
  );
}
