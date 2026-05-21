import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { cn } from '../../shared/cn';
import { Button } from './Button';

export interface OverlayProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}

export function Modal({ open, title, children, onClose, footer }: OverlayProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-text-primary/35 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className={cn('w-full max-w-lg rounded-lg border border-border bg-card shadow-soft')}>
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 id="modal-title" className="text-lg font-semibold text-text-primary">
            {title}
          </h2>
          <Button aria-label="Close modal" size="icon" variant="ghost" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <div className="px-5 py-5">{children}</div>
        {footer ? <div className="flex justify-end gap-3 border-t border-border px-5 py-4">{footer}</div> : null}
      </div>
    </div>
  );
}
