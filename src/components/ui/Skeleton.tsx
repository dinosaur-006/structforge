import type { ReactNode } from 'react';
import { cn } from '../../shared/cn';

function Skel({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cn('animate-pulse rounded-xl bg-border/60', className)} style={style} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <Skel className={className} />;
}

/** Full-width card skeleton with header, body, and footer placeholder rows. */
export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-sm">
      <Skel className="h-5 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skel key={i} className="h-4" style={{ width: `${70 - i * 15}%` }} />
      ))}
    </div>
  );
}

/** A block of text skeleton lines, e.g. for descriptions or paragraph content. */
export function SkeletonText({ lines = 4 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skel key={i} className="h-4" style={{ width: `${95 - i * 12}%` }} />
      ))}
    </div>
  );
}

/** Circular avatar/icon placeholder. */
export function SkeletonCircle({ size = 'h-10 w-10' }: { size?: string }) {
  return <Skel className={cn('rounded-full', size)} />;
}

/** Horizontal timeline placeholder with 5 segments. */
export function SkeletonTimeline() {
  return (
    <div className="space-y-4">
      <Skel className="h-5 w-32" />
      <div className="flex gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skel key={i} className="h-24 flex-1 rounded-xl" />
        ))}
      </div>
      <Skel className="h-3 w-full" />
    </div>
  );
}

/** Radar chart placeholder. */
export function SkeletonRadar() {
  return (
    <div className="flex items-center justify-center">
      <Skel className="h-[320px] w-[320px] rounded-full" />
    </div>
  );
}

/** Video player placeholder. */
export function SkeletonVideo() {
  return (
    <div className="space-y-4 rounded-xl border border-border bg-[#1A1A18] p-4 shadow-sm">
      <Skel className="aspect-[9/16] max-h-[560px] w-full rounded-xl bg-white/10 md:aspect-video" />
      <Skel className="h-2 w-full rounded-full" />
      <div className="flex justify-between">
        <Skel className="h-8 w-8 rounded-full" />
        <Skel className="h-8 w-8 rounded-full" />
      </div>
    </div>
  );
}

/** Grid of asset card skeletons. */
export function SkeletonAssetGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="space-y-2 rounded-xl border border-border p-3">
          <Skel className="aspect-video w-full" />
          <Skel className="h-4 w-3/4" />
          <Skel className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** Page-level loading wrapper that shows a skeleton until data is ready. */
export function SkeletonPage({ children, loading, fallback }: { children: ReactNode; loading: boolean; fallback: ReactNode }) {
  return loading ? <>{fallback}</> : <>{children}</>;
}

/** Full-page skeleton matching the structure of the analyze page. */
export function AnalyzePageSkeleton() {
  return (
    <section className="mx-auto max-w-[1240px] space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skel className="h-7 w-48" />
          <Skel className="h-4 w-72" />
        </div>
        <Skel className="h-10 w-28" />
      </div>
      <SkeletonCard rows={2} />
      <Skel className="h-[200px] w-full rounded-xl" />
    </section>
  );
}

/** Full-page skeleton matching the structure of the migrate page. */
export function MigratePageSkeleton() {
  return (
    <section className="mx-auto max-w-[1240px] space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skel className="h-7 w-48" />
          <Skel className="h-4 w-64" />
        </div>
        <Skel className="h-10 w-28" />
      </div>
      <SkeletonCard rows={2} />
      <SkeletonTimeline />
      <div className="grid gap-5 lg:grid-cols-[16rem,1fr]">
        <SkeletonAssetGrid count={3} />
        <SkeletonCard rows={4} />
      </div>
    </section>
  );
}

/** Full-page skeleton matching the structure of the result page. */
export function ResultPageSkeleton() {
  return (
    <section className="mx-auto max-w-[1240px] space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skel className="h-7 w-48" />
          <Skel className="h-4 w-72" />
        </div>
        <Skel className="h-10 w-28" />
      </div>
      <Skel className="h-11 w-full rounded-xl" />
      <Skel className="h-8 w-96" />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
        <SkeletonVideo />
        <SkeletonCard rows={5} />
      </div>
      <SkeletonTimeline />
      <SkeletonRadar />
    </section>
  );
}

/** Full-page skeleton for project list. */
export function ProjectListPageSkeleton() {
  return (
    <section className="mx-auto max-w-[1240px] space-y-4">
      <div className="flex items-center justify-between">
        <Skel className="h-7 w-40" />
        <Skel className="h-10 w-32" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} rows={2} />
        ))}
      </div>
    </section>
  );
}
