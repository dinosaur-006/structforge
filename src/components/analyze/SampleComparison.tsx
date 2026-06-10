import { BarChart3, CheckCircle2, Film, Timer } from 'lucide-react';
import type { AnalysisSample } from '../../shared/types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface SampleComparisonProps {
  samples: AnalysisSample[];
  onSelect: (jobId: string) => void;
}

export function SampleComparison({ samples, onSelect }: SampleComparisonProps) {
  const completed = samples.filter((sample) => sample.status === 'completed' && sample.result);
  if (!completed.length) return null;

  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">结构对比</h2>
          <p className="mt-1 text-sm text-text-secondary">追加样例后选择一个作为迁移模板；新样例不会覆盖正在编辑的结构。</p>
        </div>
        <Badge tone="neutral">{completed.length} 条样例</Badge>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {completed.map((sample, index) => {
          const structure = sample.result!;
          const product = structure.script.find((segment) => segment.type === 'product');
          return (
            <article key={sample.job_id} className="rounded-xl border border-border bg-surface p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold">样例 {index + 1}</span>
                {sample.isReference ? (
                  <Badge tone="success" icon={<CheckCircle2 className="h-3.5 w-3.5" />}>当前模板</Badge>
                ) : null}
              </div>
              <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
                <Metric icon={<Timer className="h-4 w-4" />} label="时长" value={`${structure.meta.duration}s`} />
                <Metric icon={<Film className="h-4 w-4" />} label="镜头" value={`${structure.meta.shots}`} />
                <Metric icon={<BarChart3 className="h-4 w-4" />} label="产品露出" value={product ? `${product.start}s` : '-'} />
              </dl>
              {!sample.isReference ? (
                <Button className="mt-4 w-full" size="sm" variant="secondary" onClick={() => onSelect(sample.job_id)}>
                  选择为结构模板
                </Button>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-xs text-text-secondary">{icon}{label}</dt>
      <dd className="mt-1 font-mono font-semibold text-text-primary">{value}</dd>
    </div>
  );
}
