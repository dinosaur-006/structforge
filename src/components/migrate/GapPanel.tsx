import { useState } from 'react';
import { AlertTriangle, ChevronDown } from 'lucide-react';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import type { MaterialGap } from '../../shared/types';

interface GapPanelProps {
  gaps: MaterialGap[];
  isFixing: boolean;
  onFixAll: () => void;
  onFixGap?: (gapId: string, strategy: string) => void;
}

export function GapPanel({ gaps, isFixing, onFixAll, onFixGap }: GapPanelProps) {
  const [open, setOpen] = useState(true);
  const [selectedStrategies, setSelectedStrategies] = useState<Record<string, string>>({});
  const openGaps = gaps.filter((gap) => gap.status === 'open');

  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setOpen((value) => !value)}>
        <span className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-5 w-5 text-warning" />
          {'\u7d20\u6750\u7f3a\u53e3\u8bca\u65ad'} {'\u00b7'} {openGaps.length}
        </span>
        <ChevronDown className="h-5 w-5 text-text-secondary" />
      </button>
      {open ? (
        <div className="mt-4 space-y-4">
          {gaps.map((gap) => (
            <div key={gap.id} className="rounded-lg border border-l-2 border-border border-l-warning bg-card p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={gap.severity === 'critical' ? 'error' : 'warning'}>{gap.severity === 'critical' ? '\u4e25\u91cd' : '\u8b66\u544a'}</Badge>
                <span className="font-semibold">{gap.description}</span>
                <span className="text-sm text-text-secondary">{gap.requiredSlot}</span>
              </div>
              <div className="mt-3 grid gap-2">
                {gap.strategies.map((strategy) => (
                  <label key={strategy.id} className="rounded-lg border border-border bg-sidebar/40 p-3 text-sm">
                    <span className="flex items-center gap-2 font-semibold">
                      <input
                        type="radio"
                        aria-label={strategy.name}
                        checked={strategy.id === (selectedStrategies[gap.id] ?? gap.selectedStrategyId)}
                        onChange={() => setSelectedStrategies((current) => ({ ...current, [gap.id]: strategy.id }))}
                      />
                      {strategy.name}
                    </span>
                    <span className="mt-1 block text-text-secondary">{strategy.description}</span>
                  </label>
                ))}
              </div>
              {onFixGap ? (
                <Button className="mt-3" variant="secondary" onClick={() => onFixGap(gap.id, selectedStrategies[gap.id] ?? gap.selectedStrategyId)} disabled={isFixing}>
                  {'应用选中策略'}
                </Button>
              ) : null}
            </div>
          ))}
          <Button variant="primary" onClick={onFixAll} disabled={isFixing || openGaps.length === 0}>
            {isFixing ? '\u6b63\u5728\u4fee\u590d...' : '\u4e00\u952e\u81ea\u52a8\u4fee\u590d'}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
