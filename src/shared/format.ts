import type { HealthTone } from './types';

export function formatDuration(seconds: number): string {
  return Number.isInteger(seconds) ? `${seconds}s` : `${seconds.toFixed(1)}s`;
}

export function formatRelativeTime(value: string, now = new Date()): string {
  const diff = Math.max(0, now.getTime() - new Date(value).getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${Math.max(1, minutes)}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function scoreTone(score: number): HealthTone {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'error';
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function uid(prefix: string): string {
  const random = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${random}`;
}
