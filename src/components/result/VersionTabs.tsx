import { Badge } from '../ui/Badge';
import { cn } from '../../shared/cn';
import type { ResultVersion } from '../../shared/types';

interface VersionTabsProps {
  versions: ResultVersion[];
  currentId: string;
  onChange: (id: string) => void;
}

export function VersionTabs({ versions, currentId, onChange }: VersionTabsProps) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-sidebar p-1 shadow-sm">
      {versions.map((version) => (
        <button
          key={version.id}
          type="button"
          className={cn(
            'flex min-h-11 flex-none items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors',
            version.id === currentId ? 'border-border bg-card text-text-primary shadow-sm' : 'border-transparent text-text-secondary hover:bg-card/70 hover:text-text-primary',
          )}
          onClick={() => onChange(version.id)}
        >
          {version.name}
          <Badge tone={version.score >= 80 ? 'success' : version.score >= 65 ? 'warning' : 'neutral'}>{version.score}</Badge>
        </button>
      ))}
    </div>
  );
}
