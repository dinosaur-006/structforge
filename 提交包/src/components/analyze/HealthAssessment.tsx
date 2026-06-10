import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts';
import { Badge } from '../ui/Badge';
import { scoreTone } from '../../shared/format';
import type { HealthScores } from '../../shared/types';

const healthLabels: Record<keyof HealthScores, string> = {
  hook_strength: 'Hook',
  product_exposure_timing: 'Exposure',
  selling_point_proof: 'Proof',
  pacing_compactness: 'Pacing',
  cta_persuasiveness: 'CTA',
  overall: 'Overall',
};

export function HealthAssessment({ scores }: { scores: HealthScores }) {
  const data = Object.entries(scores).map(([key, value]) => ({ metric: healthLabels[key as keyof HealthScores], score: value }));
  return (
    <div className="space-y-3">
      {/* Engine label */}
      <div className="flex items-center gap-2 text-xs">
        <span className="rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">LLM \u7efc\u5408\u8bc4\u4f30</span>
        <span className="text-text-muted">\u57fa\u4e8e\u5927\u6a21\u578b\u5bf9\u89c6\u9891\u60c5\u7eea\u3001\u8282\u594f\u3001\u5b8c\u64ad\u6f5c\u529b\u7684\u4e3b\u89c2\u5224\u65ad</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[420px,1fr]">
        <div className="min-h-[320px] rounded-xl border border-border bg-card p-4 shadow-sm">
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={data}>
              <PolarGrid stroke="#E7E5E0" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: '#6B6B65', fontSize: 12 }} />
              <Radar dataKey="score" stroke="#5C8B67" fill="#5C8B67" fillOpacity={0.2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="grid gap-3">
          {data.map((item) => (
            <div key={item.metric} className="flex items-center justify-between rounded-xl border border-border bg-card p-4 shadow-sm">
              <div>
                <p className="font-semibold">{item.metric}</p>
                <p className="text-sm text-text-secondary">AI \u76f4\u89c9\u8bc4\u5206</p>
              </div>
              <Badge tone={scoreTone(item.score)}>{item.score} / 100</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
