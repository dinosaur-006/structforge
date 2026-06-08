import { Film, Loader2, Maximize2, Pause, Play, Volume2 } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { Button } from '../ui/Button';
import type { ResultTimelineSegment } from '../../shared/types';

interface VideoPlayerProps {
  timeline: ResultTimelineSegment[];
  src?: string | null;
  onTimeUpdate?: (time: number) => void;
  isRendering?: boolean;
  renderProgress?: number;
}

export function VideoPlayer({ timeline, src, onTimeUpdate, isRendering, renderProgress = 0 }: VideoPlayerProps) {
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
  return (
    <div className="rounded-lg border border-border bg-[#0A0A10] p-4 shadow-sm">
      <div className="grid aspect-[9/16] max-h-[560px] place-items-center rounded-lg bg-[#050508] md:aspect-video">
        <div className="text-center space-y-2">
          <Film className="mx-auto h-8 w-8 text-text-muted" />
          <p className="text-sm text-text-muted">视频预览就绪后自动显示</p>
          <p className="text-xs text-text-muted">脚本已生成，正在自动渲染...</p>
        </div>
      </div>
      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-white/10">
          {timeline.map((seg) => (
            <div
              key={seg.id}
              title={seg.label}
              className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-white/20"
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
