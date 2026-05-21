import { describe, expect, it } from 'vitest';
import { formatDuration, formatRelativeTime, scoreTone } from './format';

describe('format helpers', () => {
  it('formats durations in seconds', () => {
    expect(formatDuration(35)).toBe('35s');
    expect(formatDuration(3.5)).toBe('3.5s');
  });

  it('formats known relative times', () => {
    const now = new Date('2026-05-21T12:00:00Z');
    expect(formatRelativeTime('2026-05-21T10:00:00Z', now)).toBe('2h ago');
    expect(formatRelativeTime('2026-05-20T12:00:00Z', now)).toBe('1d ago');
  });

  it('maps scores to semantic tones', () => {
    expect(scoreTone(87)).toBe('success');
    expect(scoreTone(72)).toBe('warning');
    expect(scoreTone(48)).toBe('error');
  });
});
