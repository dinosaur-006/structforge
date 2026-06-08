import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { RhythmPoint } from '../../shared/types';

function rhythmStats(data: RhythmPoint[]) {
  if (!data.length) return { avgShot: '--', peakPos: '--', peakEmotion: '--' };
  const totalCuts = data.reduce((s, p) => s + p.cuts, 0);
  const totalSeconds = Math.max(data[data.length - 1].second - data[0].second, 1);
  const avgInterval = totalCuts > 0 ? totalSeconds / totalCuts : 0;
  const peak = data.reduce((best, p) => (p.emotion > best.emotion ? p : best), data[0]);
  return {
    avgShot: `${avgInterval.toFixed(1)}s`,
    peakPos: `${peak.second.toFixed(1)}s`,
    peakEmotion: peak.emotion.toFixed(2),
  };
}

export function RhythmStructure({ data }: { data: RhythmPoint[] }) {
  const stats = rhythmStats(data);
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr,260px]">
      <div className="min-h-[280px] rounded-lg border border-border bg-card p-4 shadow-sm">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="rhythmFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="#5C8B67" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#5C8B67" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#E7E5E0" strokeDasharray="3 3" />
            <XAxis dataKey="second" stroke="#6B6B65" tick={{ fill: '#6B6B65', fontSize: 12 }} tickFormatter={(value) => `${value}s`} />
            <YAxis stroke="#6B6B65" tick={{ fill: '#6B6B65', fontSize: 12 }} />
            <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #E7E5E0', borderRadius: 8, color: '#1A1A18' }} />
            <Area type="monotone" dataKey="cuts" stroke="#5C8B67" fill="url(#rhythmFill)" strokeWidth={2} activeDot={{ r: 5, fill: '#C87D53', stroke: '#FFFFFF', strokeWidth: 2 }} dot={{ r: 3, fill: '#C87D53', strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="grid gap-4">
        {[
          ['\u5e73\u5747\u955c\u5934\u95f4\u9694', stats.avgShot],
          ['\u9ad8\u6f6e\u4f4d\u7f6e', stats.peakPos],
          ['\u60c5\u7eea\u5cf0\u503c', stats.peakEmotion],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-sm text-text-secondary">{label}</p>
            <p className="mt-2 font-mono text-2xl font-semibold text-primary">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
