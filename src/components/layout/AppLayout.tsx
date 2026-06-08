import { ChevronLeft, ChevronRight, FlaskConical, FolderOpen, HelpCircle, Menu, Sparkles, User } from 'lucide-react';
import { Suspense, useEffect } from 'react';
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
  const location = useLocation();

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
