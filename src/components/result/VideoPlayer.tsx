import { Maximize2, Pause, Play, Volume2 } from 'lucide-react';
import { useState } from 'react';
import { Button } from '../ui/Button';
import type { ResultTimelineSegment } from '../../shared/types';

export function VideoPlayer({ timeline }: { timeline: ResultTimelineSegment[] }) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(28);
  const total = Math.max(...timeline.map((segment) => segment.end), 1);

  return (
    <div className="rounded-lg border border-border bg-[#1A1A18] p-4 shadow-sm">
      <div className="grid aspect-[9/16] max-h-[560px] place-items-center rounded-lg bg-[#262622] md:aspect-video">
        <Button aria-label={playing ? 'Pause' : 'Play'} size="icon" variant="primary" onClick={() => setPlaying((value) => !value)}>
          {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </Button>
      </div>
      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-white/15">
          <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
          {timeline.map((segment) => (
            <button
              key={segment.id}
              type="button"
              title={segment.label}
              className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border border-card bg-accent"
              style={{ left: `${(segment.start / total) * 100}%` }}
              onClick={() => setProgress((segment.start / total) * 100)}
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
