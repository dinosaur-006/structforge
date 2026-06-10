import { ChevronLeft, ChevronRight, Clock, FlaskConical, FolderOpen, HelpCircle, Menu, Settings, Sparkles, User } from 'lucide-react';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Version } from '../Version';
import FAQPanel from '../shared/FAQPanel';
import { getLang, setLang, t } from '../../shared/i18n';
import { Skeleton } from '../ui/Skeleton';
import { TopProgress } from '../ui/TopProgress';
import { Modal } from '../ui/Modal';
import { cn } from '../../shared/cn';
import { copy } from '../../shared/copy';
import { useAppStore } from '../../store';

const navItemDefs = [
  { to: '/analyze',   i18nKey: 'nav.analyze',   fallback: copy.navAnalyze,   icon: Sparkles },
  { to: '/projects',  i18nKey: 'nav.projects',   fallback: copy.navProjects,  icon: FolderOpen },
  { to: '/history',   i18nKey: 'nav.history',    fallback: 'History',         icon: Clock },
  { to: '/settings',  i18nKey: 'nav.settings',   fallback: 'Settings',        icon: Settings },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const collapsed = useAppStore(s => s.sidebarCollapsed);
  const toggleSidebar = useAppStore(s => s.toggleSidebar);

  return (
    <div className="flex h-full flex-col bg-white border-r border-[#EBEAE6]">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-[#F2F0ED]">
        <div className="grid h-8 w-8 flex-none place-items-center rounded-xl bg-[#1C1C1E]">
          <Sparkles className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <span className="text-[15px] font-semibold tracking-tight text-[#1C1C1E]">
            Struct<span className="text-[#C8843C]">Forge</span>
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2.5 py-4 space-y-0.5">
        {navItemDefs.map(item => {
          const Icon = item.icon;
          const label = t(item.i18nKey, item.fallback);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) => cn(
                'flex items-center gap-2.5 h-9 px-3 rounded-xl text-[13px] font-medium transition-colors',
                isActive
                  ? 'bg-[#F5F2EC] text-[#1C1C1E]'
                  : 'text-[#8E8E93] hover:text-[#1C1C1E] hover:bg-[#FAFAF9]',
                collapsed && 'justify-center px-0 w-9 mx-auto',
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* FAQ + Language */}
      {!collapsed && (
        <div className="px-2.5 pb-3 space-y-3">
          <FAQPanel />
          <div className="flex items-center gap-1 px-1.5">
            <button onClick={() => { setLang('zh'); window.location.reload(); }}
              className={`px-2 py-1 text-[11px] rounded-md transition-colors ${getLang() === 'zh' ? 'bg-[#F5F2EC] text-[#1C1C1E] font-medium' : 'text-[#AEAEB2] hover:text-[#6E6E73]'}`}
            >中文</button>
            <button onClick={() => { setLang('en'); window.location.reload(); }}
              className={`px-2 py-1 text-[11px] rounded-md transition-colors ${getLang() === 'en' ? 'bg-[#F5F2EC] text-[#1C1C1E] font-medium' : 'text-[#AEAEB2] hover:text-[#6E6E73]'}`}
            >EN</button>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-[#F2F0ED] p-3">
        <div className={cn('flex items-center gap-2.5 px-1.5', collapsed && 'justify-center')}>
          <User className="h-4 w-4 text-[#AEAEB2] flex-shrink-0" />
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-[#AEAEB2]">Creator</p>
              <Version />
            </div>
          )}
        </div>
        <button
          onClick={toggleSidebar}
          className="hidden md:flex w-full items-center gap-2 mt-2 px-1.5 py-1.5 text-[11px] text-[#AEAEB2] hover:text-[#6E6E73] hover:bg-[#FAFAF9] rounded-xl transition-colors"
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          {!collapsed && <span>收起</span>}
        </button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const collapsed = useAppStore(s => s.sidebarCollapsed);
  const mobileOpen = useAppStore(s => s.mobileSidebarOpen);
  const setMobileOpen = useAppStore(s => s.setMobileSidebarOpen);
  const routeLoading = useAppStore(s => s.routeLoading);
  const location = useLocation();
  const [shortcutOpen, setShortcutOpen] = useState(false);

  useEffect(() => {
    useAppStore.getState().setRouteLoading(true);
    const t = window.setTimeout(() => useAppStore.getState().setRouteLoading(false), 200);
    return () => window.clearTimeout(t);
  }, [location.pathname]);

  // Global keyboard shortcut: ? to open shortcut reference
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          e.preventDefault();
          setShortcutOpen(true);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="min-h-dvh bg-[#FAFAF9]">
      <TopProgress active={routeLoading} />

      {/* Desktop sidebar */}
      <aside className={cn(
        'fixed inset-y-0 left-0 z-30 hidden md:block transition-all duration-300',
        collapsed ? 'w-[56px]' : 'w-[220px]',
      )}>
        <SidebarContent />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm md:hidden" onClick={() => setMobileOpen(false)}>
          <aside className="h-full w-64" onClick={e => e.stopPropagation()}>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className={cn('transition-all duration-300', collapsed ? 'md:pl-[56px]' : 'md:pl-[220px]')}>
        <header className="sticky top-0 z-20 flex h-11 items-center border-b border-[#EBEAE6] bg-[#FAFAF9]/80 px-4 backdrop-blur-xl md:hidden">
          <button className="p-1.5 -ml-1 rounded-xl hover:bg-[#F2F0ED] transition-colors" onClick={() => setMobileOpen(true)}>
            <Menu className="h-4 w-4 text-[#1C1C1E]" />
          </button>
          <span className="ml-3 text-[13px] font-semibold text-[#1C1C1E]">StructForge</span>
        </header>
        <main>
          <Suspense fallback={<Skeleton className="h-96 w-full" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      {/* Floating help */}
      <button
        className="fixed bottom-5 right-5 z-50 grid h-9 w-9 place-items-center rounded-full bg-white border border-[#EBEAE6] text-[#AEAEB2] hover:text-[#1C1C1E] hover:border-[#D1CFC8] shadow-sm transition-all"
        onClick={() => setShortcutOpen(true)}
        title="快捷键 (?)"
      >
        <HelpCircle className="h-4 w-4" />
      </button>

      {/* Keyboard shortcut modal */}
      <Modal open={shortcutOpen} title="快捷键" onClose={() => setShortcutOpen(false)}>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-text-secondary">自然语言编辑</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">Ctrl+K</kbd></div>
          <div className="flex justify-between"><span className="text-text-secondary">播放 / 暂停</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">Space</kbd></div>
          <div className="flex justify-between"><span className="text-text-secondary">导出视频</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">Ctrl+E</kbd></div>
          <div className="flex justify-between"><span className="text-text-secondary">保存脚本</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">Ctrl+S</kbd></div>
          <div className="flex justify-between"><span className="text-text-secondary">打开快捷键面板</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">?</kbd></div>
          <div className="flex justify-between"><span className="text-text-secondary">关闭面板 / 抽屉</span><kbd className="px-1.5 py-0.5 rounded bg-sidebar text-xs font-mono">Escape</kbd></div>
        </div>
      </Modal>
    </div>
  );
}
