import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { Button } from './Button';

export interface DrawerProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}

export function Drawer({ open, title, children, onClose, footer }: DrawerProps) {
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
    <div className="fixed inset-0 z-50 bg-text-primary/35 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <aside className="fixed inset-y-0 right-0 flex w-full flex-col border-l border-border bg-card shadow-soft md:w-[420px]">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 id="drawer-title" className="text-lg font-semibold text-text-primary">
            {title}
          </h2>
          <Button aria-label="Close drawer" size="icon" variant="ghost" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer ? <div className="flex justify-end gap-3 border-t border-border px-5 py-4">{footer}</div> : null}
      </aside>
    </div>
  );
}
