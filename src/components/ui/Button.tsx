import type { ButtonHTMLAttributes } from 'react';
import { cn } from '../../shared/cn';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'icon';
}

const variants = {
  primary: 'border-primary bg-primary text-white shadow-sm hover:border-primary-hover hover:bg-primary-hover active:border-primary-active active:bg-primary-active',
  secondary: 'border-border bg-card text-text-primary shadow-sm hover:border-primary/40 hover:bg-sidebar active:bg-border/30',
  ghost: 'border-transparent bg-transparent text-text-secondary hover:bg-sidebar hover:text-text-primary active:bg-border/40',
  danger: 'border-error/30 bg-card text-error hover:bg-error/10 active:bg-error/15',
};

const sizes = {
  sm: 'min-h-9 px-3 text-xs',
  md: 'min-h-11 px-4 text-sm',
  icon: 'h-11 w-11 p-0',
};

export function Button({ variant = 'secondary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-semibold transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:ring-offset-2 focus:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
