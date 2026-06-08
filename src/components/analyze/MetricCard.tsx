interface MetricData {
  id: string;
  name: string;
  score: number;
  evidence: string;
  raw_value: string;
  passed: boolean;
}

export function MetricCard({ metric }: { metric: MetricData }) {
  const ringColor = metric.score >= 80 ? '#10B981' : metric.score >= 50 ? '#F59E0B' : '#EF4444';
  const circumference = 2 * Math.PI * 18;
  const dashOffset = circumference - (metric.score / 100) * circumference;

  return (
    <div className={`rounded-lg border p-3 shadow-sm transition-colors ${metric.passed ? 'border-success/30 bg-success/5' : 'border-border bg-card'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{metric.name}</p>
          <p className="mt-1 text-[10px] text-text-muted leading-relaxed">{metric.evidence}</p>
          {metric.raw_value && (
            <span className="mt-1 inline-block rounded bg-sidebar px-1.5 py-0.5 text-[9px] font-mono text-text-secondary">
              {metric.raw_value}
            </span>
          )}
        </div>
        <div className="relative h-12 w-12 flex-none">
          <svg className="h-12 w-12 -rotate-90" viewBox="0 0 44 44">
            <circle cx="22" cy="22" r="18" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
            <circle
              cx="22" cy="22" r="18" fill="none"
              stroke={ringColor} strokeWidth="3" strokeLinecap="round"
              strokeDasharray={circumference} strokeDashoffset={dashOffset}
              style={{ transition: 'stroke-dashoffset 0.6s ease' }}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold" style={{ color: ringColor }}>
            {metric.score}
          </span>
        </div>
      </div>
      {metric.passed && (
        <div className="mt-1.5 flex items-center gap-1 text-[9px] text-success">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          达标
        </div>
      )}
    </div>
  );
}
