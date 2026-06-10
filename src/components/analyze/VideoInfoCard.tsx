import { Clapperboard, Clock, Image, Ruler } from 'lucide-react';
import { formatDuration } from '../../shared/format';
import type { VideoStructure } from '../../shared/types';

export function VideoInfoCard({ structure }: { structure: VideoStructure }) {
  const items = [
    { label: '\u65f6\u957f', value: formatDuration(structure.meta.duration), icon: Clock },
    { label: '\u5206\u8fa8\u7387', value: structure.meta.resolution, icon: Ruler },
    { label: '\u955c\u5934\u6570', value: `${structure.meta.shots}`, icon: Clapperboard },
    { label: '\u5c01\u9762', value: structure.meta.coverLabel, icon: Image },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="rounded-xl border border-border/60 bg-white p-4 shadow-sm">
            <Icon className="h-5 w-5 text-primary" />
            <p className="mt-3 text-xs uppercase tracking-wider text-text-secondary">{item.label}</p>
            <p className="mt-1 text-lg font-semibold">{item.value}</p>
          </div>
        );
      })}
    </div>
  );
}
