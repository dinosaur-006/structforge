import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

interface MetricRowProps {
  label: string;
  before: string;
  after: string;
  delta: string;
  positive?: boolean;
}

export function MetricRow({ label, before, after, delta, positive = true }: MetricRowProps) {
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  return (
    <div className="grid gap-2 border-b border-border py-3 text-sm last:border-b-0 sm:grid-cols-[1fr,auto,auto] sm:items-center">
      <span className="font-medium text-text-primary">{label}</span>
      <span className="font-mono text-text-secondary">{before} {'\u2192'} {after}</span>
      <span className={positive ? 'inline-flex items-center gap-1 font-semibold text-success' : 'inline-flex items-center gap-1 font-semibold text-error'}>
        <Icon className="h-4 w-4" />
        {delta}
      </span>
    </div>
  );
}
