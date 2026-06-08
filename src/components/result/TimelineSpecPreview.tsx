import { Film, Layers, Type, Volume2 } from 'lucide-react';
import { useMemo } from 'react';
import type { TimelineSpec } from '../../shared/timelineSpec';

interface Props {
  spec: TimelineSpec | null;
}

const trackIcons: Record<string, React.ReactNode> = {
  video: <Film className="h-3 w-3" />,
  subtitle: <Type className="h-3 w-3" />,
  audio: <Volume2 className="h-3 w-3" />,
};

const componentColors: Record<string, string> = {
  TitleCard: '#E85D3A',
  SplitScreen: '#8B5CF6',
  StatCard: '#3B82F6',
  QuoteCard: '#10B981',
  ProductHero: '#F59E0B',
  CTACard: '#EF4444',
  OverlayText: '#6366F1',
};

export function TimelineSpecPreview({ spec }: Props) {
  const totalFrames = spec?.composition?.totalFrames ?? 300;
  const duration = spec?.composition?.durationSeconds ?? 10;

  const clipPositions = useMemo(() => {
    if (!spec) return [];
    return spec.tracks.flatMap((track) =>
      track.clips.map((clip) => ({
        ...clip,
        trackType: track.type,
        trackLabel: track.label,
        leftPct: (clip.startFrame / totalFrames) * 100,
        widthPct: Math.max(2, (clip.durationInFrames / totalFrames) * 100),
      })),
    );
  }, [spec, totalFrames]);

  if (!spec) {
    return (
      <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-border bg-card text-sm text-text-muted">
        暂无结构化预览数据 — 请先生成脚本
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-2">
        <Layers className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">结构化时间线预览</span>
        <span className="text-xs text-text-muted">
          {spec.composition.width}x{spec.composition.height} @{spec.composition.fps}fps · {duration}s · {totalFrames} 帧
        </span>
      </div>

      {/* Time ruler */}
      <div className="flex border-b border-border/50 bg-sidebar/30 px-4 py-1">
        {Array.from({ length: Math.ceil(duration) + 1 }, (_, i) => (
          <div
            key={i}
            className="text-[9px] font-mono text-text-muted"
            style={{ width: `${(1 / duration) * 100}%` }}
          >
            {i}s
          </div>
        ))}
      </div>

      {/* Tracks */}
      {spec.tracks.map((track) => (
        <div key={track.id} className="flex border-b border-border/30 last:border-0">
          {/* Track label */}
          <div className="flex w-16 flex-none items-center gap-1 border-r border-border/30 px-2 py-3 bg-sidebar/20">
            {trackIcons[track.type] ?? <span className="h-3 w-3" />}
            <span className="text-[10px] text-text-muted truncate">{track.label}</span>
          </div>

          {/* Track content */}
          <div className="relative flex-1 py-2 px-1 min-h-[48px]">
            {track.clips.map((clip) => {
              const leftPct = (clip.startFrame / totalFrames) * 100;
              const widthPct = Math.max(2, (clip.durationInFrames / totalFrames) * 100);
              const color = componentColors[clip.component] ?? '#6366F1';
              return (
                <div
                  key={clip.id}
                  className="absolute top-1/2 -translate-y-1/2 rounded px-2 py-1.5 text-[10px] font-medium text-white truncate shadow-sm transition-transform hover:scale-[1.02] hover:z-10"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    minWidth: 28,
                  }}
                  title={`${clip.component}: ${JSON.stringify(clip.props).slice(0, 80)}`}
                >
                  {clip.component}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Component legend */}
      <div className="flex flex-wrap gap-2 border-t border-border px-4 py-2">
        {Object.entries(componentColors).map(([name, color]) => (
          <div key={name} className="flex items-center gap-1 text-[10px] text-text-muted">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
            {name}
          </div>
        ))}
      </div>
    </div>
  );
}
