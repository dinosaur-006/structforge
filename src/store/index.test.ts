import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from './index';

describe('app store', () => {
  beforeEach(() => {
    useAppStore.getState().resetForTest();
  });

  it('creates and removes projects', () => {
    const id = useAppStore.getState().addProject('Launch Clip', 'Draft');
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(true);
    useAppStore.getState().removeProject(id);
    expect(useAppStore.getState().projects.some((project) => project.id === id)).toBe(false);
  });

  it('updates a segment and supports undo redo', () => {
    useAppStore.getState().loadProjectStructure('proj-1');
    useAppStore.getState().updateSegment('seg-hook', { duration: 4, end: 4 });
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
    useAppStore.getState().undo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(3);
    useAppStore.getState().redo();
    expect(useAppStore.getState().currentStructure?.script[0].duration).toBe(4);
  });

  it('fixes gaps asynchronously', async () => {
    vi.useFakeTimers();
    const promise = useAppStore.getState().fixGaps();
    await vi.advanceTimersByTimeAsync(2100);
    await promise;
    expect(useAppStore.getState().gaps.every((gap) => gap.status === 'fixed')).toBe(true);
    vi.useRealTimers();
  });
});
