import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { sourceMeta } from '../../shared/status';
import type { ResultTimelineSegment, WaveformData } from '../../shared/types';
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
    <section className="rounded-xl border border-border bg-white shadow-sm overflow-hidden">
      {/* Header — smart legend: only show types actually present */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <SmartLegend segments={segments} />
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
          {segments.map((seg, i) => {
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
                onHover={() => loadThumbnail(seg, i, thumbnails, setThumbnails)}
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
  const [hovered, setHovered] = useState(false);
  const isDraft = segment.source === 'aigc_draft';

  return (
    <button
      type="button"
      className="relative group rounded-sm overflow-hidden transition-all hover:scale-[1.02] hover:z-10 focus-visible:ring-2 focus-visible:ring-primary/50"
      style={{
        width: `${widthPct}%`,
        minWidth: 28,
        backgroundColor: '#1a1a2e',
      }}
      onClick={onSeek}
      onMouseEnter={() => { onHover?.(); setHovered(true); }}
      onMouseLeave={() => setHovered(false)}
    >
      {/* ── LEFT color bar (4px, always visible) ── */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[4px] z-10"
        style={{ backgroundColor: meta.color }}
      />

      {/* Draft diagonal-stripe pattern overlay */}
      {isDraft && (
        <div
          className="absolute inset-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage: 'repeating-linear-gradient(-45deg, transparent, transparent 6px, rgba(200,132,60,0.12) 6px, rgba(200,132,60,0.12) 8px)',
          }}
        />
      )}

      {/* Thumbnail background */}
      {thumbnailUrl && !imgError ? (
        <img
          src={thumbnailUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-85 transition-opacity"
          onError={() => setImgError(true)}
          loading="lazy"
        />
      ) : null}

      {/* Type badge (segment type, top-left) */}
      <span
        className="absolute top-1.5 left-[7px] text-[10px] font-bold px-1.5 py-0.5 rounded z-10"
        style={{ backgroundColor: 'rgba(0,0,0,0.7)', color: '#fff' }}
      >
        {segment.label.slice(0, 6)}
      </span>

      {/* Source badge (top-right, shows on hover or always for non-original) */}
      {(hovered || segment.source !== 'original') && (
        <span
          className="absolute top-1.5 right-1.5 text-[9px] font-medium px-1.5 py-0.5 rounded z-10 flex items-center gap-1"
          style={{
            backgroundColor: `${meta.color}22`,
            color: meta.color,
            border: `1px solid ${meta.color}44`,
          }}
        >
          {isDraft && (
            <span className="inline-block w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: meta.color }} />
          )}
          {meta.label}
        </span>
      )}

      {/* BOTTOM color bar (5px, always visible) */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[5px] z-10"
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
  index: number,
  cache: Record<string, string>,
  setCache: React.Dispatch<React.SetStateAction<Record<string, string>>>,
) {
  if (cache[seg.id]) return;
  const projectId = window.location.pathname.split('/').pop() || '';
  if (!projectId) return;

  // For AI-generated segments, try Flux preview image first
  const isAI = seg.source === 'aigc' || seg.source === 'aigc_draft';
  if (isAI) {
    const fluxUrl = `${API_BASE_URL}/outputs/${projectId}/flux_previews/segment_${String(index).padStart(3, '0')}.png`;
    const img = new Image();
    img.onload = () => setCache((prev) => ({ ...prev, [seg.id]: fluxUrl }));
    img.onerror = () => {
      // Fall back to video frame thumbnail API
      const url = `${API_BASE_URL}/api/v1/optimize/${projectId}/thumbnail?t=${seg.start.toFixed(1)}`;
      fetch(url)
        .then((r) => r.json())
        .then((data) => {
          if (data?.thumbnail) setCache((prev) => ({ ...prev, [seg.id]: data.thumbnail }));
        })
        .catch(() => {});
    };
    img.src = fluxUrl;
    return;
  }

  const url = `${API_BASE_URL}/api/v1/optimize/${projectId}/thumbnail?t=${seg.start.toFixed(1)}`;
  fetch(url)
    .then((r) => r.json())
    .then((data) => {
      if (data?.thumbnail) {
        setCache((prev) => ({ ...prev, [seg.id]: data.thumbnail }));
      }
    })
    .catch(() => {});
}

// ── Smart Legend: only shows types actually in use ──

function SmartLegend({ segments }: { segments: ResultTimelineSegment[] }) {
  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const seg of segments) {
      const key = seg.source || 'original';
      map[key] = (map[key] || 0) + 1;
    }
    return map;
  }, [segments]);

  const usedTypes = Object.entries(counts);
  const hasAssets = usedTypes.some(([k]) => k !== 'original');
  const allSameType = usedTypes.length <= 1;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {usedTypes.map(([key, count]) => {
        const meta = sourceMeta[key as keyof typeof sourceMeta];
        if (!meta) return null;
        return (
          <span key={key} className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: meta.color }} />
            {meta.label}
            <span className="text-[10px] text-text-muted ml-0.5">({count})</span>
          </span>
        );
      })}
      {allSameType && !hasAssets && (
        <span className="text-[10px] text-text-muted ml-2">
          — 上传素材后解锁更多来源类型
        </span>
      )}
    </div>
  );
}
