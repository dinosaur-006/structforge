import { DndContext, type DragEndEvent } from '@dnd-kit/core';
import { horizontalListSortingStrategy, SortableContext } from '@dnd-kit/sortable';
import { SegmentBlock } from './SegmentBlock';
import type { MaterialGap, ScriptSegment } from '../../shared/types';

interface TimelineEditorProps {
  segments: ScriptSegment[];
  gaps: MaterialGap[];
  onSelect: (id: string) => void;
  onReorder: (activeId: string, overId: string) => void;
}

export function TimelineEditor({ segments, gaps, onSelect, onReorder }: TimelineEditorProps) {
  const total = segments.reduce((sum, segment) => sum + segment.duration, 0);
  const ticks = Array.from({ length: Math.floor(total / 5) + 1 }, (_, index) => index * 5);

  const handleDragEnd = (event: DragEndEvent) => {
    if (event.over && event.active.id !== event.over.id) onReorder(String(event.active.id), String(event.over.id));
  };

  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <h2 className="font-semibold">{'\u7ed3\u6784\u65f6\u95f4\u7ebf\u7f16\u8f91\u5668'}</h2>
      <div className="mt-4 pb-2">
        <DndContext onDragEnd={handleDragEnd}>
          <SortableContext items={segments.map((segment) => segment.id)} strategy={horizontalListSortingStrategy}>
            <div className="flex flex-col gap-3 sm:flex-row">
              {segments.map((segment) => (
                <SegmentBlock
                  key={segment.id}
                  segment={segment}
                  hasGap={gaps.some((gap) => gap.segmentId === segment.id && gap.status === 'open')}
                  onSelect={onSelect}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
        <div className="mt-5 hidden justify-between border-t border-border pt-3 font-mono text-xs text-text-secondary sm:flex">
          {ticks.map((tick) => <span key={tick}>{tick}s</span>)}
        </div>
      </div>
    </section>
  );
}
