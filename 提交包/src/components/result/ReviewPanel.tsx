import { Copy, Film, Image, Play } from 'lucide-react';
import { Button } from '../ui/Button';

type GenMode = 'image' | 'video';

interface ReviewPanelProps {
  segments: Array<{
    id: string; type: string; script: string; visual: string; duration: number;
    source: string; asset_id: string | null;
    camera?: string; visual_fx?: string; emotion?: string;
  }>;
  projectName: string;
  segmentModes: Record<string, GenMode>;
  segmentPrompts?: Record<string, string>;
  onModeChange: (segmentId: string, mode: GenMode) => void;
  onGenerate: () => void;
  isRendering: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  hook: 'HOOK', pain: 'PAIN', product: 'PRODUCT', proof: 'PROOF', cta: 'CTA',
};

const TYPE_COLOR: Record<string, string> = {
  hook: '#E85D3A', pain: '#8B5CF6', product: '#3B82F6', proof: '#10B981', cta: '#F59E0B',
};

export function ReviewPanel({ segments, projectName, segmentModes, segmentPrompts, onModeChange, onGenerate, isRendering }: ReviewPanelProps) {
  const aiSegments = segments.filter((s) => !s.asset_id || s.source === 'aigc');
  const origSegments = segments.filter((s) => s.asset_id && s.source !== 'aigc');
  const totalDuration = segments.reduce((sum, s) => sum + (s.duration || 0), 0);
  const videoCount = Object.values(segmentModes).filter(m => m === 'video').length;
  const imageCount = Object.values(segmentModes).filter(m => m === 'image').length;

  return (
    <div className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
      {/* Top accent line */}
      <div className="h-0.5 bg-primary/30" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary">分镜审核</h2>
            <span className="text-[10px] text-text-muted tracking-wide">Storyboard Review</span>
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="text-[11px] text-text-muted">{segments.length} 个分镜 · {totalDuration.toFixed(1)}s</span>
            <span className="h-3 w-px bg-border" />
            <span className="inline-flex items-center gap-1.5 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              <span className="text-primary font-medium">{aiSegments.length} AI</span>
            </span>
            {origSegments.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11px]">
                <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                <span className="text-accent font-medium">{origSegments.length} 原始</span>
              </span>
            )}
          </div>
        </div>
        <Button
          variant="primary"
          onClick={onGenerate}
          disabled={isRendering}
          className="min-w-[160px]"
        >
          {isRendering ? (
            <span className="flex items-center gap-2">
              <span className="inline-block h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              <span className="font-bold text-xs tracking-wide">RENDERING</span>
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Play className="h-4 w-4" />
              <span className="font-bold text-xs tracking-wide">
                {videoCount > 0
                  ? `生成 ${imageCount} 图 + ${videoCount} 视频`
                  : `生成 ${imageCount} 张图片`}
              </span>
            </span>
          )}
        </Button>
      </div>

      {/* Storyboard cards */}
      <div className="px-5 pb-4 space-y-1.5">
        {segments.map((seg, i) => {
          const isAI = !seg.asset_id || seg.source === 'aigc';
          const typeColor = TYPE_COLOR[seg.type] || '#6366F1';
          const widthPct = ((seg.duration || 1) / totalDuration) * 100;

          return (
            <div key={seg.id} className="group relative flex items-center gap-3">
              {/* Step number + accent */}
              <div className="flex-none flex flex-col items-center gap-1" style={{ width: 24 }}>
                <span className="text-[10px] font-mono font-bold text-text-muted">{String(i + 1).padStart(2, '0')}</span>
                <div className="w-0.5 flex-1 min-h-[12px] rounded-full opacity-20" style={{ backgroundColor: i < segments.length - 1 ? typeColor : 'transparent' }} />
              </div>

              {/* Card body */}
              <div
                className="flex-1 min-w-0 rounded-lg border px-4 py-2.5 transition-colors"
                style={{
                  background: isAI ? '#FDF8F2' : '#FAFAF9',
                  borderColor: isAI ? 'rgba(200,132,60,0.15)' : 'rgba(74,158,124,0.10)',
                }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="flex-none text-[10px] font-bold tracking-wider px-1.5 py-0.5 rounded"
                    style={{ color: typeColor, background: `${typeColor}12` }}
                  >
                    {TYPE_LABELS[seg.type] ?? seg.type.toUpperCase()}
                  </span>
                  <div className="flex-1 h-1 rounded-full bg-border overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${widthPct}%`, backgroundColor: isAI ? '#C8843C' : typeColor }}
                    />
                  </div>
                  <span className="flex-none text-[10px] font-mono text-text-muted">{seg.duration?.toFixed(1)}s</span>
                  <span
                    className="flex-none text-[9px] font-medium px-1.5 py-0.5 rounded-full"
                    style={{
                      color: isAI ? '#C8843C' : '#4A9E7C',
                      background: isAI ? 'rgba(200,132,60,0.08)' : 'rgba(74,158,124,0.06)',
                    }}
                  >
                    {isAI ? 'AI' : '素材'}
                  </span>
                </div>
                <p className="text-[11px] text-text-secondary mt-1.5 truncate leading-relaxed">
                  {seg.script?.slice(0, 90) || '(无脚本)'}
                </p>
                {isAI && (
                  <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-border/40">
                    <button
                      type="button"
                      className="text-[10px] text-primary/70 hover:text-primary transition-colors flex items-center gap-1"
                      onClick={() => {
                        const realPrompt = segmentPrompts?.[seg.id];
                        const text = realPrompt || `9:16 vertical, product commercial. ${seg.visual || seg.script || ''} --ar 9:16 --style raw`;
                        navigator.clipboard.writeText(text);
                      }}
                    >
                      <Copy className="h-3 w-3" />
                      复制提示词
                    </button>
                    <span className="text-[9px] text-text-muted">
                      {seg.camera || '静态'} · {seg.visual_fx || '无'} · {seg.emotion || '中性'}
                    </span>
                    <div className="ml-auto flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => onModeChange(seg.id, 'image')}
                        className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                          (segmentModes[seg.id] || 'image') === 'image'
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-text-muted hover:text-primary'
                        }`}
                      >
                        <Image className="h-3 w-3" /> 图
                      </button>
                      <button
                        type="button"
                        onClick={() => onModeChange(seg.id, 'video')}
                        className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] transition-colors ${
                          segmentModes[seg.id] === 'video'
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-text-muted hover:text-primary'
                        }`}
                      >
                        <Film className="h-3 w-3" /> 视频
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
