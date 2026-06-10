import type { ReactNode } from 'react';

interface SectionHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionHeader({ title, description, action }: SectionHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 className="font-serif text-xl font-bold tracking-tight text-text-primary">
          <span className="mr-2 inline-block h-[3px] w-6 rounded-full bg-gradient-to-r from-primary via-primary/60 to-primary/20 align-middle" />
          {title}
        </h2>
        {description ? (
          <p className="mt-2 text-sm leading-6 text-text-secondary">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex flex-none items-center gap-2">{action}</div> : null}
    </div>
  );
}
