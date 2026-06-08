import { useCallback, useEffect, useRef, useState } from 'react';
import { sourceMeta } from '../../shared/status';
import type { ResultTimelineSegment, WaveformData } from '../../shared/types';
import { SourceLegend } from '../ui/SourceLegend';
import { WaveformOverlay } from './WaveformOverlay';

interface ResultTimelineProps {
  segments: ResultTimelineSegment[];
  waveform?: WaveformData | null;
  currentTime?: number;
  onSeek: (second: number) => void;
  onTrim?: (segmentId: string, newDuration: number) => void;
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

export function ResultTimeline({ segments, waveform, currentTime, onSeek, onTrim }: ResultTimelineProps) {
  const total = segments.reduce((sum, seg) => sum + (seg.end - seg.start), 0) || 1;
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({});
  const [trimState, setTrimState] = useState<{ segId: string; edge: 'left' | 'right'; startX: number; origDuration: number } | null>(null);

  // Measure container width
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Load thumbnails lazily
  useEffect(() => {
    const projectId = segments[0]?.id ? undefined : undefined; // derive from context
    // Thumbnails are loaded on hover — see SegmentBlock
  }, [segments]);

  const handleTrimStart = useCallback(
    (segId: string, edge: 'left' | 'right', e: React.MouseEvent) => {
      e.stopPropagation();
      const seg = segments.find((s) => s.id === segId);
      if (!seg) return;
      setTrimState({ segId, edge, startX: e.clientX, origDuration: seg.end - seg.start });
      document.body.style.cursor = 'col-resize';
    },
    [segments],
  );

  useEffect(() => {
    if (!trimState) return;
    const handleMove = (e: MouseEvent) => {
      const dx = e.clientX - trimState.startX;
      const pxPerSec = containerWidth / total;
      const ds = dx / pxPerSec;
      const newDuration = Math.max(0.5, trimState.origDuration + ds);
      // Visual only during drag — commit on mouseup
    };
    const handleUp = (e: MouseEvent) => {
      const dx = e.clientX - trimState.startX;
      const pxPerSec = containerWidth / total;
      const ds = dx / pxPerSec;
      const newDuration = Math.max(0.5, trimState.origDuration + ds);
      if (Math.abs(newDuration - trimState.origDuration) > 0.1 && onTrim) {
        onTrim(trimState.segId, Math.round(newDuration * 10) / 10);
      }
      setTrimState(null);
      document.body.style.cursor = '';
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [trimState, containerWidth, total, onTrim]);

  // Time ticks
  const tickInterval = total > 60 ? 10 : total > 30 ? 5 : 3;
  const ticks: number[] = [];
  for (let t = 0; t <= total; t += tickInterval) ticks.push(t);

  return (
    <section className="rounded-lg border border-border bg-card shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <SourceLegend items={Object.values(sourceMeta).map((m) => ({ color: m.color, label: m.label }))} />
        {onTrim && (
          <span className="text-[10px] text-text-muted">拖拽分镜边缘可调整时长</span>
        )}
      </div>

      {/* Time ruler */}
      <div className="flex border-b border-border/50 bg-sidebar/50" style={{ paddingLeft: 56 }}>
        {ticks.map((t) => (
          <div
            key={t}
            className="text-[10px] font-mono text-text-muted border-l border-border/30 px-1"
            style={{ width: `${(tickInterval / total) * 100}%`, minWidth: 0 }}
          >
            {t}s
          </div>
        ))}
      </div>

      {/* Waveform track */}
      {waveform && waveform.data.length > 0 && (
        <div className="flex">
          <div className="w-14 flex-none flex items-center justify-center border-r border-border/50 bg-sidebar/30">
            <span className="text-[10px] font-medium text-text-muted -rotate-90 whitespace-nowrap">音频</span>
          </div>
          <div className="flex-1 min-w-0">
            <WaveformOverlay
              data={waveform.data}
              width={containerWidth - 56}
              height={40}
              labels={waveform.labels}
              currentTime={currentTime}
              duration={waveform.duration || total}
            />
          </div>
        </div>
      )}

      {/* Video track */}
      <div ref={containerRef} className="flex" style={{ minHeight: 72 }}>
        <div className="w-14 flex-none flex items-center justify-center border-r border-border/50 bg-sidebar/30">
          <span className="text-[10px] font-medium text-text-muted -rotate-90 whitespace-nowrap">视频</span>
        </div>
        <div className="flex-1 flex items-stretch gap-[2px] p-[2px] min-w-0">
          {segments.map((seg) => {
            const meta = sourceMeta[seg.source];
            const widthPct = Math.max(3, ((seg.end - seg.start) / total) * 100);
            return (
              <SegmentBlock
                key={seg.id}
                segment={seg}
                widthPct={widthPct}
                meta={meta}
                thumbnailUrl={thumbnails[seg.id]}
                onSeek={() => onSeek(seg.start)}
                onTrimStart={onTrim ? (edge, e) => handleTrimStart(seg.id, edge, e) : undefined}
                onHover={() => loadThumbnail(seg, thumbnails, setThumbnails)}
              />
            );
          })}
        </div>
      </div>

      {/* Subtitle track */}
      <div className="flex border-t border-border/50" style={{ minHeight: 28 }}>
        <div className="w-14 flex-none flex items-center justify-center border-r border-border/50 bg-sidebar/30">
          <span className="text-[10px] font-medium text-text-muted -rotate-90 whitespace-nowrap">字幕</span>
        </div>
        <div className="flex-1 flex items-stretch gap-[2px] p-[2px] min-w-0">
          {segments.map((seg) => {
            const widthPct = Math.max(3, ((seg.end - seg.start) / total) * 100);
            const subtitleText = seg.subtitle || seg.label || '';
            return (
              <div
                key={`sub-${seg.id}`}
                className="flex items-center overflow-hidden rounded px-1 bg-sidebar/40"
                style={{ width: `${widthPct}%`, minWidth: 0 }}
                title={subtitleText}
              >
                <span className="text-[10px] text-text-muted truncate leading-tight">
                  {subtitleText.slice(0, 40) || '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ── Segment Block ──

function SegmentBlock({
  segment,
  widthPct,
  meta,
  thumbnailUrl,
  onSeek,
  onTrimStart,
  onHover,
}: {
  segment: ResultTimelineSegment;
  widthPct: number;
  meta: { color: string; label: string; borderClass?: string };
  thumbnailUrl?: string;
  onSeek: () => void;
  onTrimStart?: (edge: 'left' | 'right', e: React.MouseEvent) => void;
  onHover?: () => void;
}) {
  const [imgError, setImgError] = useState(false);

  return (
    <button
      type="button"
      className="relative group rounded overflow-hidden transition-transform hover:scale-[1.02] hover:z-10 focus-visible:ring-2 focus-visible:ring-primary/50"
      style={{
        width: `${widthPct}%`,
        minWidth: 28,
        backgroundColor: '#1a1a2e',
      }}
      onClick={onSeek}
      onMouseEnter={onHover}
    >
      {/* Thumbnail background */}
      {thumbnailUrl && !imgError ? (
        <img
          src={thumbnailUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-70 group-hover:opacity-90 transition-opacity"
          onError={() => setImgError(true)}
          loading="lazy"
        />
      ) : null}

      {/* Type badge */}
      <span
        className="absolute top-1 left-1 text-[10px] font-bold px-1.5 py-0.5 rounded"
        style={{ backgroundColor: 'rgba(0,0,0,0.65)', color: '#fff' }}
      >
        {segment.label.slice(0, 6)}
      </span>

      {/* Source color bar */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[3px]"
        style={{ backgroundColor: meta.color }}
      />

      {/* Trim handles */}
      {onTrimStart && (
        <>
          <div
            className="absolute left-0 top-0 bottom-0 w-[6px] cursor-col-resize opacity-0 group-hover:opacity-100 bg-white/20 hover:bg-primary/50 z-20 transition-opacity"
            onMouseDown={(e) => onTrimStart('left', e)}
          />
          <div
            className="absolute right-0 top-0 bottom-0 w-[6px] cursor-col-resize opacity-0 group-hover:opacity-100 bg-white/20 hover:bg-primary/50 z-20 transition-opacity"
            onMouseDown={(e) => onTrimStart('right', e)}
          />
        </>
      )}
    </button>
  );
}

// ── Thumbnail loader ──

function loadThumbnail(
  seg: ResultTimelineSegment,
  cache: Record<string, string>,
  setCache: React.Dispatch<React.SetStateAction<Record<string, string>>>,
) {
  if (cache[seg.id]) return;
  // We need projectId — derive from URL or prop
  const projectId = window.location.pathname.split('/').pop() || '';
  if (!projectId) return;

  const url = `${API_BASE_URL}/api/v1/optimize/${projectId}/thumbnail/${seg.start.toFixed(1)}`;
  fetch(url)
    .then((r) => r.json())
    .then((data) => {
      if (data?.thumbnail) {
        setCache((prev) => ({ ...prev, [seg.id]: data.thumbnail }));
      }
    })
    .catch(() => {});
}
