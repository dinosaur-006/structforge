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
    <div className="grid gap-4 xl:grid-cols-[420px,1fr]">
      <div className="min-h-[320px] rounded-lg border border-border bg-card p-4 shadow-sm">
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
          <div key={item.metric} className="flex items-center justify-between rounded-lg border border-border bg-card p-4 shadow-sm">
            <div>
              <p className="font-semibold">{item.metric}</p>
              <p className="text-sm text-text-secondary">{'\u7ed3\u6784\u5065\u5eb7\u5ea6\u8bc4\u5206'}</p>
            </div>
            <Badge tone={scoreTone(item.score)}>{item.score} / 100</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}
