import { AlertTriangle } from 'lucide-react';
import { useState } from 'react';
import { Button } from './Button';
import { Modal } from './Modal';

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  variant?: 'danger' | 'warning';
  onConfirm: () => void;
  children: (open: () => void) => React.ReactNode;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = '确认',
  variant = 'danger',
  onConfirm,
  children,
}: ConfirmDialogProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {children(() => setOpen(true))}
      <Modal open={open} title={title} onClose={() => setOpen(false)}>
        <div className="flex gap-4">
          <AlertTriangle className={variant === 'danger' ? 'mt-0.5 h-5 w-5 flex-none text-error' : 'mt-0.5 h-5 w-5 flex-none text-warning'} />
          <div>
            <p className="text-sm leading-6 text-text-secondary">{message}</p>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
              <Button
                variant={variant === 'danger' ? 'primary' : 'secondary'}
                onClick={() => { onConfirm(); setOpen(false); }}
                className={variant === 'danger' ? 'bg-error hover:bg-error/90' : ''}
              >
                {confirmLabel}
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </>
  );
}
