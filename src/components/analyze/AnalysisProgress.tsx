import { Activity, Images, ScanSearch, SplitSquareHorizontal } from 'lucide-react';

interface AnalysisProgressProps {
  progress: number;
  stage: string;
}

export function AnalysisProgress({ progress, stage }: AnalysisProgressProps) {
  const icons = [ScanSearch, Images, SplitSquareHorizontal, Activity];
  const Icon = icons[Math.min(icons.length - 1, Math.floor(progress / 30))];

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg border border-border bg-sidebar text-primary">
            <Icon className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <p className="font-semibold">{stage}</p>
            <p className="mt-1 text-sm text-text-secondary">{'\u6b63\u5728\u89e3\u6790\u89c6\u9891\u7ed3\u6784...'}</p>
          </div>
        </div>
        <span className="font-mono text-2xl font-semibold text-primary">{progress}%</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-border">
        <div className="h-full origin-left rounded-full bg-primary transition-transform duration-700" style={{ transform: `scaleX(${progress / 100})` }} />
      </div>
    </div>
  );
}
