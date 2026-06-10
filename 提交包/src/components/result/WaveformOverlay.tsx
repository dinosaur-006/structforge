import { useEffect, useRef } from 'react';

export interface WaveformLabels {
  start: number;
  end: number;
  type: string;
}

interface WaveformOverlayProps {
  data: number[];
  width: number;
  height?: number;
  labels?: WaveformLabels[];
  currentTime?: number;
  duration: number;
  colorMap?: Record<string, string>;
}

const defaultColorMap: Record<string, string> = {
  speech: 'rgba(74, 222, 128, 0.25)',
  tts: 'rgba(74, 222, 128, 0.30)',
  bgm: 'rgba(96, 165, 250, 0.20)',
  silence: 'transparent',
};

export function WaveformOverlay({
  data,
  width,
  height = 44,
  labels,
  currentTime,
  duration,
  colorMap = defaultColorMap,
}: WaveformOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Background
    ctx.fillStyle = 'rgba(15, 15, 25, 0.6)';
    ctx.fillRect(0, 0, width, height);

    // Label regions
    if (labels && duration > 0) {
      for (const { start, end, type } of labels) {
        const x1 = (start / duration) * width;
        const x2 = (end / duration) * width;
        const color = colorMap[type] || 'transparent';
        if (color !== 'transparent') {
          ctx.fillStyle = color;
          ctx.fillRect(x1, 0, Math.max(x2 - x1, 1), height);
        }
      }
    }

    // Waveform bars
    const barWidth = Math.max(1, width / data.length - 0.5);
    const midY = height / 2;
    for (let i = 0; i < data.length; i++) {
      const amp = Math.min(1, data[i]);
      const barHeight = amp * (height - 4);
      const x = i * (width / data.length);
      const y = midY - barHeight / 2;

      // Gradient from subtle to bright based on amplitude
      const alpha = 0.3 + amp * 0.7;
      ctx.fillStyle = `rgba(180, 200, 220, ${alpha.toFixed(2)})`;
      ctx.fillRect(x, y, barWidth, Math.max(1, barHeight));
    }

    // Center line
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(width, midY);
    ctx.stroke();

    // Playback pointer
    if (currentTime !== undefined && currentTime > 0 && duration > 0) {
      const px = (currentTime / duration) * width;
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, height);
      ctx.stroke();

      // Pointer head
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(px, 4, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [data, width, height, labels, currentTime, duration, colorMap]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded-t-md"
      style={{ height, display: 'block' }}
      aria-label="音频波形"
    />
  );
}
