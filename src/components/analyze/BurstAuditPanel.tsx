import { Award, ChevronDown, ChevronRight, Sparkles, Target, Zap } from 'lucide-react';
import { useState } from 'react';
import { MetricCard } from './MetricCard';

interface DimensionData {
  name: string;
  score: number;
  strengths: string[];
  weaknesses: string[];
  metrics: Array<{
    id: string;
    name: string;
    score: number;
    evidence: string;
    raw_value: string;
    passed: boolean;
  }>;
}

interface AuditReport {
  overall_score: number;
  dimensions: DimensionData[];
  suggestions: Array<{ target?: string; action: string; expected_effect: string }>;
  llm_insights: Record<string, unknown>;
  burst_template: Record<string, unknown>;
}

const dimIcons: Record<string, React.ReactNode> = {
  '注意力': <Zap className="h-4 w-4 text-[#E85D3A]" />,
  '信任': <Award className="h-4 w-4 text-[#3B82F6]" />,
  '卖点': <Target className="h-4 w-4 text-[#10B981]" />,
  '节奏': <Sparkles className="h-4 w-4 text-[#8B5CF6]" />,
  '转化': <Zap className="h-4 w-4 text-[#F59E0B]" />,
};

export function BurstAuditPanel({ report }: { report: AuditReport | null }) {
  const [expandedDims, setExpandedDims] = useState<Set<string>>(new Set(['注意力锚点 (Hook)']));

  if (!report) {
    return (
      <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-border bg-card text-sm text-text-muted">
        暂无审计数据 — 请先完成视频分析
      </div>
    );
  }

  const toggleDim = (name: string) => {
    setExpandedDims((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const overallColor = report.overall_score >= 80 ? '#10B981' : report.overall_score >= 55 ? '#F59E0B' : '#EF4444';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-card px-5 py-4">
        <div>
          <h2 className="font-semibold text-sm">全模态爆款审计报告</h2>
          <p className="text-xs text-text-muted mt-0.5">32项指标 × 5维度 × 4模态量化分析</p>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color: overallColor }}>{report.overall_score}</div>
          <div className="text-[10px] text-text-muted">综合爆款指数</div>
        </div>
      </div>

      {/* LLM unavailable banner */}
      {report.llm_insights && (report.llm_insights as Record<string, unknown>).error && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-amber-400/80">
          LLM 软分析暂时不可用（{(report.llm_insights as Record<string, unknown>).error as string}），
          当前展示基于 32 项规则量化的硬指标结果。建议稍后重试以获取 AI 改进建议。
        </div>
      )}

      {/* Suggestions */}
      {report.suggestions.length > 0 && (
        <div className="rounded-lg border border-primary/20 bg-primary-muted p-4">
          <p className="text-xs font-semibold text-primary mb-2">AI 改进建议</p>
          <div className="space-y-2">
            {report.suggestions.slice(0, 3).map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary flex-none" />
                <div>
                  <span className="font-medium">{s.action}</span>
                  <span className="text-text-muted ml-1">— {s.expected_effect}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dimensions */}
      {report.dimensions.map((dim) => {
        const isExpanded = expandedDims.has(dim.name);
        const dimKey = Object.keys(dimIcons).find((k) => dim.name.includes(k)) || '';
        const icon = dimIcons[dimKey] ?? <Target className="h-4 w-4" />;
        const dimColor = dim.score >= 80 ? '#10B981' : dim.score >= 50 ? '#F59E0B' : '#EF4444';

        return (
          <div key={dim.name} className="rounded-lg border border-border bg-card overflow-hidden">
            {/* Dimension header */}
            <button
              type="button"
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-sidebar/30 transition-colors"
              onClick={() => toggleDim(dim.name)}
            >
              <div className="flex items-center gap-3">
                {icon}
                <div>
                  <p className="text-sm font-semibold">{dim.name}</p>
                  <div className="flex gap-2 mt-0.5">
                    {dim.strengths.slice(0, 2).map((s) => (
                      <span key={s} className="text-[9px] text-success bg-success/10 rounded px-1 py-0.5">{s}</span>
                    ))}
                    {dim.weaknesses.slice(0, 2).map((w) => (
                      <span key={w} className="text-[9px] text-error bg-error/10 rounded px-1 py-0.5">{w}</span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold" style={{ color: dimColor }}>{dim.score}</span>
                {isExpanded ? <ChevronDown className="h-4 w-4 text-text-muted" /> : <ChevronRight className="h-4 w-4 text-text-muted" />}
              </div>
            </button>

            {/* Metrics grid */}
            {isExpanded && (
              <div className="border-t border-border px-3 py-3">
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {dim.metrics.map((m) => (
                    <MetricCard key={m.id} metric={m} />
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Template summary */}
      {report.burst_template && Object.keys(report.burst_template).length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-semibold mb-2">爆款创作参数模板</p>
          <div className="grid grid-cols-3 gap-1 text-[10px]">
            {Object.entries(report.burst_template).slice(0, 12).map(([key, val]) => (
              <div key={key} className="flex justify-between rounded bg-sidebar/50 px-2 py-1">
                <span className="text-text-muted">{key}</span>
                <span className="font-mono text-text-primary">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
