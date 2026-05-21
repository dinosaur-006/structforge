import type { ReactNode } from 'react';
import { cn } from '../../shared/cn';

export interface BadgeProps {
  children: ReactNode;
  tone?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  icon?: ReactNode;
  className?: string;
}

const tones = {
  success: 'border-success/30 bg-card text-success',
  warning: 'border-warning/40 bg-card text-[#8A6425]',
  error: 'border-error/35 bg-card text-error',
  info: 'border-accent/35 bg-card text-accent',
  neutral: 'border-border bg-card text-text-secondary',
};

export function Badge({ children, tone = 'neutral', icon, className }: BadgeProps) {
  return (
    <span className={cn('inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold', tones[tone], className)}>
      {icon}
      {children}
    </span>
  );
}
