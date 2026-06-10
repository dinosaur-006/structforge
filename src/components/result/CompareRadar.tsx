import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts';
import type { HealthScores } from '../../shared/types';

const labels: Record<keyof HealthScores, string> = {
  hook_strength: 'Hook',
  product_exposure_timing: 'Exposure',
  selling_point_proof: 'Proof',
  pacing_compactness: 'Pacing',
  cta_persuasiveness: 'CTA',
  overall: 'Overall',
};

export function CompareRadar({ original, current }: { original: HealthScores; current: HealthScores }) {
  const data = Object.keys(labels).map((key) => ({
    metric: labels[key as keyof HealthScores],
    original: original[key as keyof HealthScores],
    current: current[key as keyof HealthScores],
  }));

  return (
    <section className="min-h-[320px] rounded-xl border border-border bg-card p-4 shadow-sm">
      <h2 className="font-semibold">{'\u7ed3\u6784\u5bf9\u6bd4'}</h2>
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={data}>
          <PolarGrid stroke="#E7E5E0" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#6B6B65', fontSize: 12 }} />
          <Radar dataKey="original" stroke="#9E9A90" fill="#D4D0C8" fillOpacity={0.15} strokeDasharray="4 4" />
          <Radar dataKey="current" stroke="#5C8B67" fill="#5C8B67" fillOpacity={0.2} />
        </RadarChart>
      </ResponsiveContainer>
    </section>
  );
}
