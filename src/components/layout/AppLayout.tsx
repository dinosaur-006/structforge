import { ChevronLeft, ChevronRight, Cpu, FlaskConical, FolderOpen, HelpCircle, Menu, Sparkles, User } from 'lucide-react';
import { Suspense, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Version } from '../Version';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';
import { TopProgress } from '../ui/TopProgress';
import { cn } from '../../shared/cn';
import { copy } from '../../shared/copy';
import { useAppStore } from '../../store';

const navItems = [
  { to: '/analyze', label: copy.navAnalyze, icon: FlaskConical },
  { to: '/projects', label: copy.navProjects, icon: FolderOpen },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <div className="flex h-full flex-col bg-sidebar text-text-primary scanline-subtle">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border px-4">
        <div className="grid h-10 w-10 flex-none place-items-center rounded-lg bg-primary-muted ring-1 ring-primary/20">
          <Sparkles className="h-5 w-5 text-primary" />
        </div>
        {!collapsed ? (
          <span className="font-serif text-lg font-bold tracking-tight text-primary">
            Struct<span className="text-text-primary">Forge</span>
          </span>
        ) : null}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-5">
        {navItems.map((item, i) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex min-h-11 items-center gap-3 rounded-lg border px-3 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'border-primary/20 bg-primary-muted text-primary shadow-glow'
                    : 'border-transparent text-text-secondary hover:border-border-visible hover:bg-card-hover hover:text-text-primary',
                  collapsed && 'justify-center px-0',
                )
              }
              style={{ animationDelay: `${i * 50}ms` }}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-4.5 w-4.5 flex-none" />
              {!collapsed ? <span>{item.label}</span> : null}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="space-y-2 border-t border-border p-3">
        <div className={cn('flex min-h-11 items-center gap-3 rounded-lg px-3', collapsed && 'justify-center px-0')}>
          <User className="h-4.5 w-4.5 text-text-muted" />
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-text-secondary">Creator</p>
              <Version />
            </div>
          ) : null}
        </div>
        <button
          aria-label="Toggle sidebar"
          className="hidden w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-text-muted transition-colors hover:bg-card-hover hover:text-text-secondary md:flex"
          onClick={toggleSidebar}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed ? <span>Collapse</span> : null}
        </button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const mobileOpen = useAppStore((s) => s.mobileSidebarOpen);
  const setMobileOpen = useAppStore((s) => s.setMobileSidebarOpen);
  const routeLoading = useAppStore((s) => s.routeLoading);
  const setRouteLoading = useAppStore((s) => s.setRouteLoading);
  const apiCapabilities = useAppStore((s) => s.apiCapabilities);
  const blueprintPayloads = useAppStore((s) => s.blueprintPayloads);
  const location = useLocation();
  const [indicatorHovered, setIndicatorHovered] = useState(false);

  // Pre-viz mode indicator logic
  const preVizStatus = useMemo(() => {
    if (apiCapabilities.videoGen || !apiCapabilities.loaded) return null;
    const count = blueprintPayloads?.payloads?.length ?? 0;
    if (count === 0) return null;
    const cost = blueprintPayloads?.total_estimated_cost_usd ?? 0;
    return { count, cost };
  }, [apiCapabilities, blueprintPayloads]);

  useEffect(() => {
    setRouteLoading(true);
    const t = window.setTimeout(() => setRouteLoading(false), 200);
    return () => window.clearTimeout(t);
  }, [location.pathname, setRouteLoading]);

  return (
    <div className="min-h-dvh bg-surface text-text-primary">
      {/* Studio color bars — video production reference */}
      <div className="fixed inset-x-0 top-0 z-50 color-bars" />
      <TopProgress active={routeLoading} />

      {/* Desktop sidebar */}
      <aside className={cn('fixed inset-y-0 left-0 z-30 hidden border-r border-border transition-all duration-300 md:block', collapsed ? 'w-16' : 'w-60')}>
        <SidebarContent />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden" onClick={() => setMobileOpen(false)}>
          <aside className="h-full w-72 border-r border-border" onClick={(e) => e.stopPropagation()}>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      {/* Main */}
      <div className={cn('transition-all duration-300', collapsed ? 'md:pl-16' : 'md:pl-60')}>
        <header className="sticky top-0 z-20 flex h-12 items-center border-b border-border bg-surface/80 px-4 backdrop-blur-xl md:hidden">
          <Button aria-label="Menu" size="icon" variant="ghost" onClick={() => setMobileOpen(true)}>
            <Menu className="h-4 w-4" />
          </Button>
        </header>
        <main className="min-h-dvh p-4 md:p-8 xl:p-10">
          <Suspense fallback={<Skeleton className="h-96 w-full" />}>
            <Outlet />
          </Suspense>
        </main>

        {/* ── Pre-viz Mode Global Indicator ── */}
        {preVizStatus ? (
          <div
            className="fixed top-4 right-4 z-50 select-none"
            onMouseEnter={() => setIndicatorHovered(true)}
            onMouseLeave={() => setIndicatorHovered(false)}
          >
            {/* Floating indicator pill */}
            <div className={cn(
              'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-300',
              'border-[#FFB300]/30 bg-[#0A0A10]/90 backdrop-blur-md shadow-lg',
              indicatorHovered ? 'border-[#FFB300]/60 shadow-[0_0_20px_rgba(255,179,0,0.15)]' : '',
            )}>
              {/* Pulsing amber dot */}
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FFB300] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FFB300]" />
              </span>
              <span className="text-[#FFB300]">Pre-viz 离线模式</span>
              <span className="text-text-muted">·</span>
              <span className="text-text-secondary font-mono">{preVizStatus.count} 个预留位</span>
              {indicatorHovered ? (
                <Cpu className="h-3.5 w-3.5 text-[#FFB300] animate-pulse" />
              ) : (
                <span className="text-[10px] text-text-muted font-mono">${preVizStatus.cost.toFixed(2)}</span>
              )}
            </div>

            {/* Hover tooltip */}
            {indicatorHovered ? (
              <div className="absolute top-full right-0 mt-2 w-72 rounded-lg border border-[#FFB300]/20 bg-[#0A0A10]/95 backdrop-blur-xl p-4 shadow-[0_0_30px_rgba(255,179,0,0.08)] animate-in">
                <p className="text-xs font-semibold text-[#FFB300] flex items-center gap-1.5 mb-2">
                  <Cpu className="h-3.5 w-3.5" />
                  离线 Pre-viz 导演分镜模式
                </p>
                <p className="text-xs text-text-secondary leading-relaxed mb-3">
                  系统已完成物理引擎层面的{preVizStatus.count}个分镜规划。填入 Seedance API Key 后，
                  AI 将自动生成真实视频画面替换蓝图卡片。当前模式下音频（TTS · BGM）完整播放。
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded bg-[#FFB300]/5 px-2 py-1.5">
                    <span className="text-text-muted">预留位数</span>
                    <p className="font-mono font-bold text-text-primary">{preVizStatus.count}</p>
                  </div>
                  <div className="rounded bg-[#FFB300]/5 px-2 py-1.5">
                    <span className="text-text-muted">预估算力成本</span>
                    <p className="font-mono font-bold text-green-400">${preVizStatus.cost.toFixed(2)}</p>
                  </div>
                </div>
                <p className="mt-2 text-[10px] text-text-muted leading-relaxed">
                  底层 AI 模型可替换为 Sora / Runway / Kling，Payload 结构通用。
                </p>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Floating help button */}
        <button
          type="button"
          aria-label="帮助"
          title="快捷键: Ctrl+K = 自然语言编辑, Ctrl+Z = 撤销, Space = 播放/暂停"
          className="fixed bottom-6 right-6 z-50 grid h-10 w-10 place-items-center rounded-full border border-border-visible bg-card text-text-muted shadow-raised transition-all hover:border-primary/40 hover:text-primary hover:shadow-glow"
          onClick={() => {
            // Simple alert with key shortcuts - replace with modal in production
            const shortcuts = 'Ctrl+K: 自然语言编辑 | Ctrl+Z: 撤销 | Ctrl+Shift+Z: 重做 | Delete: 删除分镜 | Space: 播放/暂停 | Ctrl+E: 导出';
            alert(shortcuts);
          }}
        >
          <HelpCircle className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
