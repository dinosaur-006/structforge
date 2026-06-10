import type { ButtonHTMLAttributes } from 'react';
import { cn } from '../../shared/cn';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'icon';
}

const variants = {
  primary:
    'border-primary/20 bg-primary text-surface font-semibold shadow-glow hover:border-primary/40 hover:bg-primary-hover active:bg-primary-active transition-all duration-200',
  secondary:
    'border-border-visible bg-card text-text-primary hover:border-primary/30 hover:bg-card-hover active:bg-card-raised transition-all duration-200',
  ghost:
    'border-transparent bg-transparent text-text-secondary hover:bg-card-hover hover:text-text-primary active:bg-card-raised transition-all duration-200',
  danger:
    'border-error/30 bg-error-muted text-error hover:bg-error/20 active:bg-error/30 transition-all duration-200',
};

const sizes = {
  sm: 'min-h-9 px-3 text-xs rounded-md',
  md: 'min-h-11 px-4 text-sm rounded-xl',
  icon: 'h-10 w-10 p-0 rounded-xl',
};

export function Button({ variant = 'secondary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 border font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-40',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
