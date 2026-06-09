import { Film, Grid3X3, Loader2, Maximize2, Pause, Play, Volume2 } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { Button } from '../ui/Button';
import type { ResultTimelineSegment } from '../../shared/types';

interface VideoPlayerProps {
  timeline: ResultTimelineSegment[];
  src?: string | null;
  onTimeUpdate?: (time: number) => void;
  isRendering?: boolean;
  renderProgress?: number;
  hasDraftSegments?: boolean;
  onBlueprintClick?: () => void;
}

export function VideoPlayer({
  timeline,
  src,
  onTimeUpdate,
  isRendering,
  renderProgress = 0,
  hasDraftSegments = false,
  onBlueprintClick,
}: VideoPlayerProps) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const total = Math.max(...timeline.map((seg) => seg.end), 1);
  const videoRef = useRef<HTMLVideoElement>(null);

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (video && onTimeUpdate) {
      onTimeUpdate(video.currentTime);
      setProgress((video.currentTime / total) * 100);
    }
  }, [onTimeUpdate, total]);

  const handleSeek = useCallback((sec: number) => {
    const video = videoRef.current;
    if (video) {
      video.currentTime = sec;
      setProgress((sec / total) * 100);
    }
  }, [total]);

  // ── Real video available ──
  if (src) {
    return (
      <div className="rounded-lg border border-border bg-[#0A0A10] p-4 shadow-sm">
        <video
          ref={videoRef}
          data-testid="rendered-video"
          className="aspect-[9/16] max-h-[560px] w-full rounded-lg bg-[#050508] object-contain md:aspect-video"
          src={src}
          controls
          onTimeUpdate={handleTimeUpdate}
        />
        <div className="relative mt-2 h-2 rounded-full bg-white/10">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
          {timeline.map((seg) => (
            <button
              key={seg.id}
              type="button"
              title={seg.label}
              className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border border-card bg-accent hover:scale-125 transition-transform"
              style={{ left: `${(seg.start / total) * 100}%` }}
              onClick={() => handleSeek(seg.start)}
            />
          ))}
        </div>
      </div>
    );
  }

  // ── Rendering in progress ──
  if (isRendering) {
    return (
      <div className="rounded-lg border border-primary/20 bg-[#0A0A10] p-4 shadow-sm">
        <div className="grid aspect-[9/16] max-h-[560px] place-items-center rounded-lg bg-[#050508] md:aspect-video">
          <div className="text-center space-y-4">
            <div className="relative">
              <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary/60" />
              <Film className="absolute inset-0 mx-auto h-10 w-10 text-primary/20" />
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary">视频渲染中...</p>
              <p className="text-xs text-text-muted mt-1">AI 正在合成画面、配音和字幕</p>
            </div>
            {/* Render progress bar */}
            <div className="mx-auto w-48">
              <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${Math.max(5, renderProgress)}%` }}
                />
              </div>
              <p className="text-[10px] text-text-muted mt-1.5 font-mono">{renderProgress}%</p>
            </div>
          </div>
        </div>
        {/* Timeline scrubber dots (inactive) */}
        <div className="relative mt-2 h-2 rounded-full bg-white/10">
          {timeline.map((seg) => (
            <div
              key={seg.id}
              title={seg.label}
              className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-white/20"
              style={{ left: `${(seg.start / total) * 100}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  // ── No video yet (baseline / before any render) ──
  const draftSegments = timeline.filter((s) => s.source === 'aigc_draft' || !s.subtitle);

  return (
    <div className="rounded-lg border border-border bg-[#0A0A10] p-4 shadow-sm">
      <div className="grid aspect-[9/16] max-h-[560px] place-items-center rounded-lg bg-[#050508] md:aspect-video">
        {/* Blueprint prompt preview */}
        {hasDraftSegments && draftSegments.length > 0 ? (
          <div className="w-full h-full flex flex-col p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-flex h-2 w-2 rounded-full bg-[#FFB300] animate-pulse" />
              <span className="text-xs font-medium text-[#FFB300]">
                AI 蓝图草稿 — 以下提示词可直接用于文生视频
              </span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2">
              {draftSegments.slice(0, 3).map((seg) => (
                <div key={seg.id} className="rounded-md border border-[#FFB300]/15 bg-[#0A0A10] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-medium text-text-muted">
                      {seg.label} · {seg.subtitle || seg.script || '(无文案)'}
                    </span>
                    <button
                      type="button"
                      className="text-[10px] text-[#FFB300] hover:underline"
                      onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(seg.subtitle || seg.script || ''); }}
                    >
                      复制
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
                    9:16 竖屏，商业广告风格，写实高清。{seg.subtitle || seg.script || seg.label}
                  </p>
                </div>
              ))}
              {draftSegments.length > 3 && (
                <p className="text-[10px] text-text-muted text-center">
                  ...还有 {draftSegments.length - 3} 个分镜，点击下方查看全部
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center space-y-2">
            <Film className="mx-auto h-8 w-8 text-text-muted" />
            <p className="text-sm text-text-muted">视频预览就绪后自动显示</p>
            <p className="text-xs text-text-muted">脚本已生成，正在自动渲染...</p>
          </div>
        )}
      </div>

      {/* Blueprint action bar */}
      {hasDraftSegments && (
        <div className="mt-2 rounded-md border border-[#FFB300]/20 bg-[#FFB300]/5 px-3 py-2 flex items-center gap-3">
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-[#FFB300] hover:text-[#FFC107] transition-colors"
            onClick={onBlueprintClick}
          >
            <Grid3X3 className="h-3.5 w-3.5" />
            查看完整 Payload 与成本预估
          </button>
          <button
            type="button"
            className="ml-auto text-[10px] text-text-muted hover:text-text-secondary transition-colors"
            onClick={() => {
              const prompts = draftSegments.map((s) => `[${s.label}] ${s.subtitle || s.script || ''}`).join('\n\n');
              navigator.clipboard.writeText(prompts);
            }}
          >
            一键复制全部提示词
          </button>
        </div>
      )}

      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-white/10">
          {timeline.map((seg) => (
            <div
              key={seg.id}
              title={`${seg.label}${seg.source === 'aigc_draft' ? ' [DRAFT]' : ''}`}
              className={`absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full ${
                seg.source === 'aigc_draft'
                  ? 'bg-[#FFB300] animate-pulse'
                  : 'bg-white/20'
              }`}
              style={{ left: `${(seg.start / total) * 100}%` }}
            />
          ))}
        </div>
        <div className="mt-3 flex justify-between">
          <Button size="icon" variant="ghost" aria-label="Volume"><Volume2 className="h-5 w-5" /></Button>
          <Button size="icon" variant="ghost" aria-label="Fullscreen"><Maximize2 className="h-5 w-5" /></Button>
        </div>
      </div>
    </div>
  );
}
