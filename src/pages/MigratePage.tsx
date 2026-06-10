import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AssetPanel } from '../components/migrate/AssetPanel';
import { CreativeBriefPanel } from '../components/migrate/CreativeBriefPanel';
import { NLEditInput } from '../components/migrate/NLEditInput';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';
import { SectionHeader } from '../components/ui/SectionHeader';
import { WorkflowSteps } from '../components/layout/WorkflowSteps';
import { copy } from '../shared/copy';
import type { FinalScriptStyle } from '../shared/types';
import { useAppStore } from '../store';

const styleOptions: Array<{ value: string; label: string }> = [
  { value: 'advised', label: '标准' },
  { value: 'conversion', label: '高转化' },
  { value: 'premium', label: '高质感' },
];

const styleMap: Record<string, FinalScriptStyle> = {
  advised: 'default',
  conversion: 'high_conversion',
  premium: 'high_quality',
};

export default function MigratePage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const [style, setStyle] = useState('advised');
  const [structureChecked, setStructureChecked] = useState(false);

  const routeLoading = useAppStore((s) => s.routeLoading);
  const findProject = useAppStore((s) => s.findProject);
  const project = findProject(projectId);
  const currentStructure = useAppStore((s) => s.currentStructure);
  const scriptLoading = useAppStore((s) => s.scriptLoading);
  const assets = useAppStore((s) => s.assets);
  const assetLoading = useAppStore((s) => s.assetLoading);
  const gaps = useAppStore((s) => s.gaps);

  const fetchProjects = useAppStore((s) => s.fetchProjects);
  const loadProjectStructure = useAppStore((s) => s.loadProjectStructure);
  const updateProjectBrief = useAppStore((s) => s.updateProjectBrief);
  const migrateScript = useAppStore((s) => s.migrateScript);
  const nlEdit = useAppStore((s) => s.nlEdit);
  const uploadAsset = useAppStore((s) => s.uploadAsset);

  // ── Compute suggested brief DURING render (before useEffect fires) ──
  const suggestedBrief = useMemo(() => {
    if (!currentStructure || !project) return null;
    const brief = project.brief;
    const existingName = brief?.productName?.trim() || '';
    const isGarbage = !existingName
      || (existingName.length > 8 && !/[一-龥]/.test(existingName))
      || /^\S{15,}$/.test(existingName);
    if (!isGarbage) return null; // brief is already valid, don't override

    const productSeg = currentStructure.script.find(s => s.type === 'product');
    const proofSeg = currentStructure.script.find(s => s.type === 'proof');
    const coverLabel = currentStructure.meta?.coverLabel as string | undefined;
    const llmProductName = currentStructure.meta?.productName as string | undefined;

    const rawCopy = _clean(productSeg?.copy);
    const productName = _clean(llmProductName)
      || _findProductName(rawCopy)
      || _findProductName(_clean(coverLabel))
      || _findProductName(_clean(project.name || ''));

    const points: string[] = [];
    const pt1 = _shorten(rawCopy);
    if (pt1 && pt1.length >= 3) points.push(pt1);
    const pt2 = _shorten(_clean(proofSeg?.copy));
    if (pt2 && pt2.length >= 3 && pt2 !== pt1) points.push(pt2);
    const pt3 = _clean(productSeg?.visual || '').slice(0, 30);
    if (pt3 && pt3.length >= 3 && !points.includes(pt3)) points.push(pt3);

    return { productName: productName || '', sellingPoints: points };
  }, [currentStructure, project?.brief, project?.name]);

  // ── Page load: fetch project, load structure ──
  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!projectId) return;
      setStructureChecked(false);
      await fetchProjects();
      const routed = useAppStore.getState().findProject(projectId);
      if (!routed) {
        if (!cancelled) setStructureChecked(true);
        return;
      }
      if (routed.status === 'draft' || routed.status === 'analyzing') {
        if (!cancelled) navigate(`/analyze?projectId=${projectId}`, { replace: true });
        return;
      }
      try {
        await loadProjectStructure(projectId);
      } catch {
        // error toast already in store
      } finally {
        if (!cancelled) setStructureChecked(true);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [fetchProjects, loadProjectStructure, navigate, projectId]);

  // ── Generate and auto-navigate ──
  const handleGenerate = async () => {
    const script = await migrateScript(projectId, styleMap[style] ?? 'default');
    if (script) navigate(`/result/${projectId}`);
  };

  // ── Derived state ──

  if (routeLoading) {
    return (
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
        <WorkflowSteps current="migrate" projectId={projectId} />
        <div className="flex min-h-[300px] items-center justify-center rounded-xl border border-border/60 bg-white">
          <div className="text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
            <p className="mt-3 text-sm text-text-secondary">正在加载项目数据…</p>
          </div>
        </div>
      </section>
    );
  }

  if (!currentStructure && structureChecked) {
    return (
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
        <ErrorAlert
          title="无法加载项目"
          description="项目不存在或结构数据未初始化，请回到项目列表重试"
          action={
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => navigate('/projects')}>返回项目列表</Button>
              <Button variant="primary" onClick={() => { setStructureChecked(false); void loadProjectStructure(projectId); }}>重新加载</Button>
            </div>
          }
        />
      </section>
    );
  }

  if (!currentStructure) {
    // Edge case: not loading, not checked, but no structure. Show loading.
    return (
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
        <WorkflowSteps current="migrate" projectId={projectId} />
        <div className="flex min-h-[300px] items-center justify-center rounded-xl border border-border/60 bg-white">
          <div className="text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
            <p className="mt-3 text-sm text-text-secondary">正在加载…</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 pt-8 sm:pt-12 lg:pt-14 pb-28 space-y-4">
      <WorkflowSteps current="migrate" projectId={projectId} />

      {/* ── Header ── */}
      <SectionHeader
        title="AI 正在优化你的视频结构"
        description={`${project?.name ?? projectId} · AI 已自动完成素材匹配和缺口补全`}
      />


      {/* ── 素材缺口识别 — 赛题展示用 ── */}
      {gaps.length > 0 && (
        <div className="rounded-xl border border-border/60 bg-white px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <h2 className="text-sm font-semibold text-text-primary">素材缺口识别</h2>
            <span className="text-xs text-text-muted">({gaps.length} 个结构槽位需要素材)</span>
          </div>
          <div className="space-y-2">
            {gaps.map(gap => {
              const segLabel = {hook:'开头吸引',pain:'痛点场景',product:'产品展示',proof:'信任背书',cta:'转化引导'}[gap.segmentId?.split('-')[1] || ''] || gap.segmentId;
              const availableStrategies = gap.strategies?.filter((s: any) => s.available) || [];
              return (
                <div key={gap.id} className="flex items-start gap-3 rounded-lg border border-border/40 bg-sidebar/50 px-3 py-2.5">
                  <span className={`mt-0.5 h-2 w-2 rounded-full flex-none ${gap.severity === 'critical' ? 'bg-warning' : 'bg-text-muted'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-primary">{gap.severity === 'critical' ? '⚠️ 关键缺口' : '缺口'}: {segLabel}</p>
                    <p className="text-[11px] text-text-secondary mt-0.5">{gap.description}</p>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {availableStrategies.map((s: any) => (
                        <span key={s.id} className="text-[9px] text-accent bg-accent/8 rounded px-1.5 py-0.5">
                          {s.name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[10px] text-text-muted">
            渲染时 ComfyUI Flux 将自动为缺失画面生成 AI 图片。上述策略为推荐补全方式，实际渲染使用 AIGC 方案。
          </p>
        </div>
      )}

      {/* ── 创作简报（必要的人工输入） ── */}
      <CreativeBriefPanel
        brief={project?.brief}
        suggested={suggestedBrief}
        projectId={projectId}
        onSave={(brief) => updateProjectBrief(projectId, brief)}
      />

      {/* ── AI 自然语言调整（可选） ── */}
      <div className="rounded-xl border border-border/60 bg-card px-5 py-4">
        <p className="mb-3 text-sm text-text-secondary">
          对 AI 生成的结构不满意？用一句话告诉 AI 怎么改：
        </p>
        <NLEditInput onCommand={(cmd) => nlEdit(cmd)} loading={routeLoading} />
      </div>

      {/* ── 素材上传与管理 ── */}
      <div className="rounded-xl border border-border/60 bg-card px-5 py-4">
        <p className="mb-3 text-sm font-medium text-text-primary">
          上传产品素材（可选，上传后可自动匹配空缺分镜，减少 AI 生成需求）
        </p>
        <AssetPanel
          assets={assets}
          assetLoading={assetLoading}
          onUploadAsset={(file) => uploadAsset(file)}
          projectId={projectId}
        />
      </div>

      {/* ── Bottom action bar ── */}
      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-border/40 bg-white/90 px-6 py-3.5 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1240px] items-center justify-between">
          <p className="text-sm text-text-secondary">
            确认商品信息后，选择风格生成视频脚本
          </p>
          <div className="flex items-center gap-3">
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              aria-label="风格"
              className="h-10 rounded-xl border border-border bg-sidebar px-3 text-sm font-medium text-text-primary outline-none"
            >
              {styleOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <Button
              variant="primary"
              disabled={scriptLoading}
              onClick={() => void handleGenerate()}
            >
              {scriptLoading ? '生成中...' : copy.generateVideo}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Text extraction helpers ──

/** Strip production params 【镜】【字】【速】【情】【视】 from text. */
function _clean(text: string | undefined | null): string {
  if (!text) return '';
  return text
    .replace(/【[镜字速情视]】[^\s【】]{1,10}(?:\([^)]*\))?/g, '')
    .replace(/【[镜字速情视]】/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Extract a product name from Chinese text.
 *
 *  "就是这个从小吃到大的旺旺泡芙，谁的童年回忆里没它呀" → "旺旺泡芙"
 *  "猜我今天挖到什么童年封神零食？！" → "童年封神零食"
 *
 *  Strategy (tried in order):
 *  1. Text after 的 before ，/。 — "XX的【产品名】"
 *  2. Text after 到/了 before ，/。 — "挖到【产品名】"
 *  3. Last 2-6 Chinese chars before clause end
 */
function _findProductName(text: string): string {
  if (!text) return '';
  // Remove common filler words that appear at the start
  let t = text.replace(/^(就是|这个|那个|这是|那是|一款|一瓶|一包|一盒)/, '');

  // Strategy 1: "XX的【产品名】" pattern
  let m = t.match(/的([一-鿿]{2,6})(?:，|。|！|？|,|$)/);
  if (m) return m[1];

  // Strategy 2: "挖到/吃到/用了【产品名】" pattern
  m = t.match(/(?:到|了|过)([一-鿿]{2,6})(?:，|。|！|？|,|$)/);
  if (m) return m[1];

  // Strategy 3: last meaningful Chinese phrase before clause end
  // Strip sentence-final particles
  t = t.replace(/[吧呀啦哦呢吗嘛啊的！，。？]+$/, '');
  // Take last 2-6 chars if they're all Chinese
  m = t.match(/([一-鿿]{2,6})$/);
  if (m) return m[1];

  // Strategy 4: first 2-6 Chinese chars that aren't stop words
  const stopWords = new Set(['这个', '那个', '从小', '童年', '今天', '我们', '大家', '真的', '感觉', '就是', '一个']);
  const globalMatch = t.match(/[一-鿿]{2,6}/g);
  if (globalMatch) {
    for (const candidate of globalMatch) {
      if (!stopWords.has(candidate)) return candidate;
    }
    return globalMatch[0];
  }

  return '';
}

/** Truncate to max 30 chars at a word boundary. */
function _shorten(text: string): string {
  if (!text) return '';
  return text.length <= 30 ? text : text.slice(0, 28) + '…';
}
