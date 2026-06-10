import { AudioLines, Eye, ImagePlus, Server, Sparkles } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Capabilities, CapabilityItem } from '../../shared/types';
import { Badge } from '../ui/Badge';

const items: Array<{ key: keyof Capabilities; Icon: typeof Sparkles }> = [
  { key: 'llm', Icon: Sparkles },
  { key: 'vision', Icon: Eye },
  { key: 'asr', Icon: AudioLines },
  { key: 'aigc', Icon: ImagePlus },
  { key: 'taskExecution', Icon: Server },
];

export function CapabilityStatusPanel({ capabilities }: { capabilities: Capabilities }) {
  return (
    <section className="rounded-xl border border-border/60 bg-white p-4 shadow-sm" aria-label="能力运行状态">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-text-primary">能力运行状态</h2>
        <span className="text-xs text-text-secondary">仅显示配置状态，真实可用性以执行结果为准</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {items.map(({ key, Icon }) => (
          <CapabilityStatusItem key={key} item={capabilities[key]} icon={<Icon className="h-4 w-4" />} />
        ))}
      </div>
    </section>
  );
}

function CapabilityStatusItem({ item, icon }: { item: CapabilityItem; icon: ReactNode }) {
  const tone = item.state === 'configured' || item.state === 'worker' ? 'success' : item.state === 'fallback' || item.state === 'inline' ? 'warning' : 'neutral';
  const stateLabel = item.state === 'configured' ? '已配置' : item.state === 'worker' ? '异步' : item.state === 'fallback' ? '回退' : item.state === 'inline' ? '本地' : '未启用';

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-text-primary">{icon}{item.label}</span>
        <Badge tone={tone}>{stateLabel}</Badge>
      </div>
      <p className="mt-2 text-xs leading-5 text-text-secondary">{item.detail}</p>
    </div>
  );
}
