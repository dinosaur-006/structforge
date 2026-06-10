import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertCircle, Lock } from 'lucide-react';
import { cn } from '../../shared/cn';
import { formatDuration, scoreTone } from '../../shared/format';
import type { ScriptSegment } from '../../shared/types';

const toneClasses = {
  success: 'border-l-success',
  warning: 'border-l-warning',
  error: 'border-l-error',
};

interface SegmentBlockProps {
  segment: ScriptSegment;
  hasGap: boolean;
  onSelect: (id: string) => void;
}

export function SegmentBlock({ segment, hasGap, onSelect }: SegmentBlockProps) {
  const { setNodeRef, transform, transition } = useSortable({ id: segment.id });
  const tone = scoreTone(segment.healthScore);

  return (
    <button
      ref={setNodeRef}
      type="button"
      className={cn('relative min-h-32 min-w-0 flex-1 rounded-xl border border-l-2 border-border bg-card p-4 text-left shadow-sm transition-colors hover:border-primary/40', toneClasses[tone])}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      onClick={() => onSelect(segment.id)}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-text-primary">{segment.label}</p>
          <p className="mt-1 text-sm text-text-secondary">{segment.start}-{segment.end}s</p>
        </div>
        <div className="flex gap-1">
          {hasGap ? <AlertCircle className="h-4 w-4 text-error" /> : null}
          {segment.locked ? <Lock className="h-4 w-4" /> : null}
        </div>
      </div>
      <p className="mt-5 font-mono text-xl font-semibold text-text-primary">{formatDuration(segment.duration)}</p>
      <p className="mt-1 text-xs text-text-secondary">{'\u5065\u5eb7\u5ea6'} {segment.healthScore}</p>
    </button>
  );
}
