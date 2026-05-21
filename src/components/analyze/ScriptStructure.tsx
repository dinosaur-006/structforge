import { useState } from 'react';
import { cn } from '../../shared/cn';
import type { ScriptSegment } from '../../shared/types';

const segmentColors = {
  hook: 'border-l-primary',
  pain: 'border-l-warning',
  product: 'border-l-accent',
  proof: 'border-l-success',
  cta: 'border-l-error',
};

export function ScriptStructure({ segments }: { segments: ScriptSegment[] }) {
  const [selectedId, setSelectedId] = useState(segments[0]?.id);
  const total = segments.reduce((sum, segment) => sum + segment.duration, 0);
  const selected = segments.find((segment) => segment.id === selectedId) ?? segments[0];

  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold">{'\u53d9\u4e8b\u6bb5\u843d'} {'\u00b7'} {segments.length} {'\u4e2a\u5206\u955c\u7247\u6bb5'}</h3>
        <div className="mt-4 grid gap-3 sm:flex">
          {segments.map((segment) => (
            <button
              key={segment.id}
              type="button"
              className={cn('min-h-24 rounded-lg border border-l-2 border-border bg-card p-3 text-left shadow-sm transition-colors hover:border-primary/40', segmentColors[segment.type])}
              style={{ flexBasis: `${(segment.duration / total) * 100}%` }}
              onClick={() => setSelectedId(segment.id)}
            >
              <p className="font-semibold text-text-primary">{segment.label}</p>
              <p className="mt-1 text-xs text-text-secondary">{segment.start}-{segment.end}s</p>
              <p className="mt-3 text-sm text-text-secondary">{'\u5065\u5eb7\u5ea6'} {segment.healthScore}</p>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <div className="rounded-lg border border-border bg-sidebar/60 p-5">
          <p className="text-sm text-text-secondary">{'\u7c7b\u578b'}</p>
          <h4 className="mt-1 text-lg font-semibold">{selected.label}</h4>
          <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <p><span className="text-text-secondary">{'\u76ee\u6807\uff1a'}</span>{selected.goal}</p>
            <p><span className="text-text-secondary">{'\u5065\u5eb7\u5ea6\uff1a'}</span>{selected.healthScore}</p>
            <p className="md:col-span-2"><span className="text-text-secondary">{'\u6587\u6848\uff1a'}</span>{selected.copy}</p>
            <p className="md:col-span-2"><span className="text-text-secondary">{'\u5173\u952e\u89c6\u89c9\uff1a'}</span>{selected.visual}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
