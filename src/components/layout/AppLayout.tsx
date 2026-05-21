import { ChevronLeft, ChevronRight, FlaskConical, FolderOpen, Menu, Settings, User, Wand2 } from 'lucide-react';
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
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  return (
    <div className="flex h-full flex-col bg-sidebar text-text-primary">
      <div className="flex h-16 items-center gap-3 border-b border-border px-4">
        <div className="grid h-10 w-10 flex-none place-items-center rounded-lg border border-border bg-card">
          <Wand2 className="h-5 w-5 text-primary" />
        </div>
        {!collapsed ? <span className="text-lg font-semibold tracking-tight">StructForge</span> : null}
      </div>

      <nav className="flex-1 space-y-1 px-3 py-5">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex min-h-11 items-center gap-3 rounded-lg border px-3 text-sm font-semibold transition-colors',
                  isActive ? 'border-border bg-card text-text-primary shadow-sm' : 'border-transparent text-text-secondary hover:bg-card/70 hover:text-text-primary',
                  collapsed && 'justify-center px-0',
                )
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-5 w-5 flex-none" />
              {!collapsed ? <span>{item.label}</span> : null}
            </NavLink>
          );
        })}
      </nav>

      <div className="space-y-3 border-t border-border p-3">
        <div className={cn('flex min-h-11 items-center gap-3 rounded-lg border border-border bg-card px-3', collapsed && 'justify-center px-0')}>
          <User className="h-5 w-5 text-primary" />
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">Demo User</p>
              <Version />
            </div>
          ) : null}
          {!collapsed ? <Settings className="h-4 w-4 text-text-secondary" /> : null}
        </div>
        <Button aria-label="Toggle sidebar" variant="ghost" className="hidden w-full md:flex" onClick={toggleSidebar}>
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          {!collapsed ? <span>{'\u6536\u8d77'}</span> : null}
        </Button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const mobileOpen = useAppStore((state) => state.mobileSidebarOpen);
  const setMobileOpen = useAppStore((state) => state.setMobileSidebarOpen);
  const routeLoading = useAppStore((state) => state.routeLoading);
  const setRouteLoading = useAppStore((state) => state.setRouteLoading);
  const location = useLocation();

  useEffect(() => {
    setRouteLoading(true);
    const timer = window.setTimeout(() => setRouteLoading(false), 250);
    return () => window.clearTimeout(timer);
  }, [location.pathname, setRouteLoading]);

  return (
    <div className="min-h-dvh bg-surface text-text-primary">
      <TopProgress active={routeLoading} />
      <aside className={cn('fixed inset-y-0 left-0 z-30 hidden border-r border-border transition-all duration-300 md:block', collapsed ? 'w-16' : 'w-60')}>
        <SidebarContent />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 bg-text-primary/35 md:hidden" onClick={() => setMobileOpen(false)}>
          <aside className="h-full w-72 border-r border-border" onClick={(event) => event.stopPropagation()}>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className={cn('transition-all duration-300', collapsed ? 'md:pl-16' : 'md:pl-60')}>
        <header className="sticky top-0 z-20 flex h-14 items-center border-b border-border bg-surface/90 px-4 backdrop-blur md:hidden">
          <Button aria-label="Open navigation" size="icon" variant="ghost" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
        </header>
        <main className="min-h-dvh p-4 md:p-6 xl:p-8">
          <Suspense fallback={<Skeleton className="h-96 w-full" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
