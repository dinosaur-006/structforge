import { cn } from '../../shared/cn';

/**
 * Metric data contract — kept backward-compatible with BurstAuditPanel.
 * The component derives visual state from ``passed`` and ``score``.
 */
interface MetricData {
  id: string;
  name: string;
  score: number;
  evidence: string;
  raw_value: string;
  passed: boolean;
}

/** Top-edge neon glow gradient by score tier. */
const GLOW_GRADIENT: Record<string, string> = {
  emerald: 'from-emerald-500/60',
  amber: 'from-amber-500/60',
  red: 'from-red-500/60',
};

const scoreTier = (score: number) =>
  score >= 80 ? 'emerald' : score >= 50 ? 'amber' : 'red';

/** Glow-dot indicator — the user's "status dot with shadow" concept. */
const DOT_STYLE: Record<string, string> = {
  emerald: 'bg-emerald-400 shadow-[0_0_8px_rgba(74,158,124,0.4)]',
  amber: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]',
  red: 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]',
};

export function MetricCard({ metric }: { metric: MetricData }) {
  const tier = scoreTier(metric.score);
  const ringColor =
    metric.score >= 80 ? '#10B981' : metric.score >= 50 ? '#F59E0B' : '#EF4444';
  const circumference = 2 * Math.PI * 18;
  const dashOffset = circumference - (metric.score / 100) * circumference;

  return (
    <div
      className={cn(
        'relative flex flex-col p-5 overflow-hidden transition-all duration-300',
        'bg-white rounded-2xl border border-[#EBEAE6] shadow-[0_1px_3px_rgba(0,0,0,0.02)] hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]',
        'group',
      )}
    >
      {/* ── Top-edge accent line ── */}
      <div
        className={cn(
          'absolute top-0 left-1/4 w-1/2 h-px bg-gradient-to-r to-transparent',
          'from-transparent via-current',
          GLOW_GRADIENT[tier],
        )}
        style={{ color: ringColor }}
      />

      {/* Header row */}
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-sm font-medium text-[#6E6E73] truncate flex-1 min-w-0">
          {metric.name}
        </h3>

        <div className="flex items-center gap-2 flex-none ml-2">
          {metric.raw_value && (
            <span className="px-2 py-0.5 text-[10px] font-medium text-[#6E6E73] bg-[#FAFAF9] rounded-full border border-[#EBEAE6]">
              {metric.raw_value}
            </span>
          )}
          <span className={cn('w-2 h-2 rounded-full', DOT_STYLE[tier])} />
        </div>
      </div>

      {/* Score + ring */}
      <div className="flex items-center gap-4 mb-3">
        <span className="text-3xl font-light text-[#1C1C1E]">
          {metric.score}
        </span>
        <div className="relative h-10 w-10 flex-none">
          <svg className="h-10 w-10 -rotate-90" viewBox="0 0 44 44">
            <circle cx="22" cy="22" r="18" fill="none" stroke="#EBEAE6" strokeWidth="3" />
            <circle cx="22" cy="22" r="18" fill="none"
              stroke={ringColor} strokeWidth="3" strokeLinecap="round"
              strokeDasharray={circumference} strokeDashoffset={dashOffset}
              style={{ transition: 'stroke-dashoffset 0.8s ease' }}
            />
          </svg>
        </div>
      </div>

      {metric.evidence && (
        <p className="text-xs text-[#AEAEB2] mt-auto line-clamp-2 leading-relaxed">
          {metric.evidence}
        </p>
      )}
    </div>
  );
}
