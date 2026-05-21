import { sourceMeta } from '../../shared/status';
import type { ResultTimelineSegment } from '../../shared/types';
import { SourceLegend } from '../ui/SourceLegend';

interface ResultTimelineProps {
  segments: ResultTimelineSegment[];
  onSeek: (second: number) => void;
}

export function ResultTimeline({ segments, onSeek }: ResultTimelineProps) {
  const total = segments.reduce((sum, segment) => sum + (segment.end - segment.start), 0);
  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <SourceLegend items={Object.values(sourceMeta).map((meta) => ({ color: meta.color, label: meta.label }))} />
      <div className="mt-4 grid gap-3 sm:flex">
        {segments.map((segment) => {
          const meta = sourceMeta[segment.source];
          return (
            <button
              key={segment.id}
              type="button"
              className={`min-h-20 rounded-lg border border-l-2 border-border bg-card p-3 text-left shadow-sm transition-colors hover:border-primary/40 ${meta.borderClass}`}
              style={{ flexBasis: `${((segment.end - segment.start) / total) * 100}%` }}
              onClick={() => onSeek(segment.start)}
            >
              <p className="font-semibold text-text-primary">{segment.label}</p>
              <p className="mt-1 text-xs text-text-secondary">{meta.label}</p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
