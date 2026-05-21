import { cn } from '../../shared/cn';

export function TopProgress({ active }: { active: boolean }) {
  return (
    <div className={cn('fixed left-0 top-0 z-[70] h-0.5 w-full overflow-hidden transition-opacity', active ? 'opacity-100' : 'opacity-0')}>
      <div className="h-full w-1/2 origin-left animate-[progress_1s_ease-in-out_infinite] bg-primary" />
    </div>
  );
}
