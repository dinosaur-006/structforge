import { useEffect, useState, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../services/api';
import type { Project } from '../shared/types';
import { Clock, Play, Film, AlertCircle, Search, SlidersHorizontal } from 'lucide-react';

type FilterStatus = 'all' | 'completed' | 'processing' | 'draft';

const GLYPHS: Record<string, { label: string; color: string }> = {
  completed:  { label: '已渲染',  color: '#4A9E7C' },
  processing: { label: '进行中', color: '#C8843C' },
  analyzing:  { label: '分析中',  color: '#C8843C' },
  failed:     { label: '失败',    color: '#D45A5A' },
  draft:      { label: '草稿',     color: '#AEAEB2' },
};

export default function HistoryPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [search, setSearch] = useState('');

  const fetchProjects = useCallback(async () => {
    setLoading(true); setError(null);
    try { setProjects(await api.listProjects() as Project[]); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Failed to load'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const { filtered, counts } = useMemo(() => {
    let r = [...projects];
    if (filter !== 'all') r = r.filter(p => p.status === filter);
    if (search) r = r.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));
    r.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    const c = { all: projects.length, completed: 0, processing: 0, draft: 0 };
    projects.forEach(p => {
      if (p.status === 'completed') c.completed++;
      else if (p.status === 'processing' || p.status === 'analyzing') c.processing++;
      else c.draft++;
    });
    return { filtered: r, counts: c };
  }, [projects, filter, search]);

  const fmtDate = (d: string) => { try { return new Date(d).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }); } catch { return d; } };

  const navigateToProject = (p: Project) => {
    switch (p.status) {
      case 'draft':
      case 'analyzing':
        navigate(`/analyze?projectId=${p.id}`);
        break;
      case 'editing':
        navigate(`/migrate/${p.id}`);
        break;
      case 'completed':
      case 'rendering':
      default:
        navigate(`/result/${p.id}`);
        break;
    }
  };

  return (
    <div>
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14">
        {/* Header */}
        <header className="mb-8">
          <p className="text-xs tracking-[0.15em] text-[#C8843C]/70 font-medium mb-2">历史记录</p>
          <div className="flex items-center justify-between">
            <h1 className="text-[28px] sm:text-[34px] font-semibold tracking-tight text-[#1C1C1E]">项目历史</h1>
            <button onClick={fetchProjects} className="text-[13px] text-[#6E6E73] hover:text-[#1C1C1E] transition-colors font-medium">
              刷新
            </button>
          </div>
          <p className="text-sm text-[#8E8E93] mt-1.5">
            {projects.length} 个项目 &middot; {counts.completed} 已完成 &middot; {counts.processing} 进行中
          </p>
        </header>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 mb-8 pb-6 border-b border-[#EBEAE6]">
          <SlidersHorizontal className="w-3.5 h-3.5 text-[#AEAEB2] mr-1" />
          {(['all', 'completed', 'processing', 'draft'] as FilterStatus[]).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-[12px] font-medium px-3 py-1.5 rounded-xl transition-colors ${
                filter === f ? 'bg-[#F5F2EC] text-[#1C1C1E]' : 'text-[#8E8E93] hover:text-[#1C1C1E] hover:bg-[#FAFAF9]'
              }`}
            >{f === 'all' ? '全部' : f === 'completed' ? '已完成' : f === 'processing' ? '进行中' : '草稿'}
              <span className="ml-1 text-[#AEAEB2]">{counts[f]}</span>
            </button>
          ))}
          <div className="flex-1" />
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#AEAEB2]" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="搜索…"
              className="w-44 pl-8 pr-3 py-2 text-[13px] bg-white border border-[#EBEAE6] focus:border-[#C8843C]/30 rounded-xl text-[#1C1C1E] placeholder:text-[#C4C2BB] outline-none transition-colors"
            />
          </div>
        </div>

        {/* Content */}
        {loading && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="aspect-[9/16] bg-[#F2F0ED] rounded-xl mb-3" />
                <div className="h-3 bg-[#F2F0ED] rounded w-3/4 mb-1.5" />
                <div className="h-2.5 bg-[#F2F0ED] rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-24">
            <AlertCircle className="w-8 h-8 text-[#D45A5A]/50 mx-auto mb-3" />
            <p className="text-sm text-[#6E6E73] mb-4">{error}</p>
            <button onClick={fetchProjects} className="text-[13px] font-medium text-[#C8843C] hover:text-[#B07530] transition-colors">重试</button>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-24">
            <Film className="w-10 h-10 text-[#D1CFC8] mx-auto mb-4" />
            <p className="text-lg font-medium text-[#6E6E73] mb-1">暂无项目</p>
            <p className="text-sm text-[#AEAEB2] mb-6">{filter !== 'all' ? '尝试其他筛选条件' : '创建你的第一个项目'}</p>
            <Link to="/projects" className="inline-block text-[13px] font-medium text-[#C8843C] hover:text-[#B07530] transition-colors">前往项目 →</Link>
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {filtered.map(p => {
              const g = GLYPHS[p.status] || GLYPHS.draft;
              return (
                <div key={p.id} onClick={() => navigateToProject(p)}
                  className="group cursor-pointer rounded-xl bg-white border border-[#EBEAE6] shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:border-[#D1CFC8] transition-all duration-300"
                >
                  <div className="aspect-[9/16] mx-3 mt-3 rounded-xl bg-[#FAFAF9] flex items-center justify-center relative overflow-hidden">
                    {p.status === 'completed' ? (
                      <div className="w-12 h-12 rounded-full bg-white border border-[#EBEAE6] shadow-sm flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                        <Play className="w-4 h-4 text-[#1C1C1E] ml-0.5" fill="currentColor" />
                      </div>
                    ) : p.status === 'processing' || p.status === 'analyzing' ? (
                      <div className="w-7 h-7 border-2 border-[#EBEAE6] border-t-[#C8843C]/60 rounded-full animate-spin" />
                    ) : (
                      <Film className="w-6 h-6 text-[#D1CFC8]" />
                    )}
                    <div className="absolute top-2 left-2 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: g.color }} />
                      <span className="text-[10px] font-medium text-[#8E8E93]">{g.label}</span>
                    </div>
                    {p.status === 'completed' && (
                      <div className="absolute bottom-2 right-2 text-[10px] text-[#AEAEB2] bg-white/80 px-1.5 py-0.5 rounded-md">
                        <Play className="w-3 h-3" fill="currentColor" />
                      </div>
                    )}
                  </div>
                  <div className="p-3">
                    <h3 className="text-[13px] font-medium text-[#1C1C1E] truncate group-hover:text-[#C8843C] transition-colors">
                      {p.name || 'Untitled'}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-[#AEAEB2]">
                      <Clock className="w-3 h-3" />
                      <span>{fmtDate(p.updatedAt)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!loading && !error && (
          <footer className="mt-10 pt-5 border-t border-[#EBEAE6] flex items-center justify-between text-[11px] text-[#AEAEB2]">
            <span>{projects.length} 条记录</span>
            <span>
              <span style={{ color: '#4A9E7C' }}>{counts.completed} 已渲染</span>
              <span className="mx-2 text-[#D1CFC8]">/</span>
              <span style={{ color: '#C8843C' }}>{counts.processing} 进行中</span>
              <span className="mx-2 text-[#D1CFC8]">/</span>
              <span>{counts.draft} 草稿</span>
            </span>
          </footer>
        )}
      </section>
    </div>
  );
}
