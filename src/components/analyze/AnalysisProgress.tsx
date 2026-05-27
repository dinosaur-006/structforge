import { Activity, Images, ScanSearch, SplitSquareHorizontal } from 'lucide-react';
import { useEffect, useState } from 'react';

interface AnalysisProgressProps {
  progress: number;
  stage: string;
}

export function AnalysisProgress({ progress, stage }: AnalysisProgressProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const icons = [ScanSearch, Images, SplitSquareHorizontal, Activity];
  const normalizedProgress = Math.max(0, Math.min(100, Math.round(progress)));
  const waitingForMeasuredProgress = normalizedProgress === 0;
  const elapsedLabel = formatElapsed(elapsedSeconds);
  const Icon = icons[Math.min(icons.length - 1, Math.floor(normalizedProgress / 30))];

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setElapsedSeconds((seconds) => seconds + 1);
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, []);

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg border border-border bg-sidebar text-primary">
            <Icon className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <p className="font-semibold">{stage}</p>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-text-secondary">
              <span>{'\u6b63\u5728\u89e3\u6790\u89c6\u9891\u7ed3\u6784...'}</span>
              <span aria-hidden="true">{'\u00b7'}</span>
              <span>{`\u5df2\u7528\u65f6 ${elapsedLabel}`}</span>
            </p>
          </div>
        </div>
        <span className="min-w-[5.5rem] text-right font-mono text-xl font-semibold text-primary sm:text-2xl">
          {waitingForMeasuredProgress ? '\u5904\u7406\u4e2d' : `${normalizedProgress}%`}
        </span>
      </div>
      <div
        aria-busy="true"
        aria-label={'\u89c6\u9891\u5206\u6790\u8fdb\u5ea6'}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={waitingForMeasuredProgress ? undefined : normalizedProgress}
        aria-valuetext={
          waitingForMeasuredProgress
            ? `\u6b63\u5728\u5904\u7406\u4e2d\uff0c\u5df2\u7528\u65f6 ${elapsedLabel}`
            : `${normalizedProgress}%\uff0c\u5df2\u7528\u65f6 ${elapsedLabel}`
        }
        className="mt-4 h-2 overflow-hidden rounded-full bg-border"
        role="progressbar"
      >
        {waitingForMeasuredProgress ? (
          <div className="h-full w-1/3 rounded-full bg-primary animate-[progress_1.25s_ease-in-out_infinite]" />
        ) : (
          <div
            className="relative h-full origin-left overflow-hidden rounded-full bg-primary transition-transform duration-700"
            style={{ transform: `scaleX(${normalizedProgress / 100})` }}
          >
            <span className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-white/30 animate-[progress_1.25s_ease-in-out_infinite]" />
          </div>
        )}
      </div>
    </div>
  );
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remainder = (seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
}
