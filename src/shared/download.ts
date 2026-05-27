import type { FinalScript } from './types';

export function downloadJson(filename: string, payload: unknown): void {
  downloadText(filename, `${JSON.stringify(payload, null, 2)}\n`, 'application/json;charset=utf-8');
}

export function downloadText(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function finalScriptToSrt(script: FinalScript): string {
  const captions = script.segments.map((segment, index) => [
    String(index + 1),
    `${srtTime(segment.start)} --> ${srtTime(segment.end)}`,
    segment.script,
  ].join('\n'));
  return `${captions.join('\n\n')}\n`;
}

export function safeFileStem(value: string): string {
  return value.trim().replace(/[\\/:*?"<>|]+/g, '_') || 'structforge';
}

function srtTime(seconds: number): string {
  const totalMilliseconds = Math.round(Math.max(seconds, 0) * 1000);
  const milliseconds = totalMilliseconds % 1000;
  const totalSeconds = Math.floor(totalMilliseconds / 1000);
  const secondsPart = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutesPart = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);

  return `${pad(hours)}:${pad(minutesPart)}:${pad(secondsPart)},${String(milliseconds).padStart(3, '0')}`;
}

function pad(value: number): string {
  return String(value).padStart(2, '0');
}
