import { Columns2, Download, GitBranch, History, ShieldAlert, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AIReview } from '../components/result/AIReview';
import { CompareRadar } from '../components/result/CompareRadar';
import { ExportDialog } from '../components/result/ExportDialog';
import { ResultTimeline } from '../components/result/ResultTimeline';
import { TimelineSpecPreview } from '../components/result/TimelineSpecPreview';
import { VersionTabs } from '../components/result/VersionTabs';
import { VideoPlayer } from '../components/result/VideoPlayer';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';
import { MetricRow } from '../components/ui/MetricRow';
import { SectionHeader } from '../components/ui/SectionHeader';
import { WorkflowSteps } from '../components/layout/WorkflowSteps';
import { copy } from '../shared/copy';
import { downloadJson, downloadText, finalScriptToSrt, safeFileStem } from '../shared/download';
import { api } from '../services/api';
import type { FinalScriptStyle, RenderResolution, RenderVersion, WaveformData } from '../shared/types';
import { useAppStore } from '../store';

const scriptVersionLabel: Record<string, string> = {
  high_click: '\u9ad8\u70b9\u51fb\u7248',
  high_conversion: '\u9ad8\u8f6c\u5316\u7248',
  fast_pace: '\u5feb\u8282\u594f\u7248',
  high_quality: '\u9ad8\u8d28\u611f\u7248',
  xiaohongshu_ces: '\u5c0f\u7ea2\u4e66CES\u7834\u5c40\u7248',
  wechat_social: '\u5fae\u4fe1\u89c6\u9891\u53f7\u88c2\u53d8\u7248',
  default: '\u9ed8\u8ba4\u7248',
};

const renderVersionMap: Record<string, RenderVersion> = {
  original: 'original',
  default: 'original',
  high_click: 'strong_hook',
  high_conversion: 'strong_conversion',
  fast_pace: 'safe_fix',
  high_quality: 'original',
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

export default function ResultPage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const [exportOpen, setExportOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [projectsChecked, setProjectsChecked] = useState(false);
  const [waveform, setWaveform] = useState<WaveformData | null>(null);
  const [playbackTime, setPlaybackTime] = useState(0);
  const fetchProjects = useAppStore((state) => state.fetchProjects);
  const loadFinalScript = useAppStore((state) => state.loadFinalScript);
  const fetchResultVersions = useAppStore((state) => state.fetchResultVersions);
  const findProject = useAppStore((state) => state.findProject);
  const project = findProject(projectId);
  const currentScript = useAppStore((state) => state.currentScript);
  const versions = useAppStore((state) => state.versions);
  const evaluationLabel = useAppStore((state) => state.evaluationLabel);
  const currentVersionId = useAppStore((state) => state.currentVersionId);
  const setVersion = useAppStore((state) => state.setVersion);
  const isExporting = useAppStore((state) => state.isExporting);
  const renderProgress = useAppStore((state) => state.renderProgress);
  const outputUrl = useAppStore((state) => state.outputUrl);
  const startRender = useAppStore((state) => state.startRender);
  const currentVersion = useMemo(() => versions.find((version) => version.id === currentVersionId) ?? versions[0], [currentVersionId, versions]);
  const original = versions[0];

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!useAppStore.getState().projects.length) await fetchProjects();
      await fetchResultVersions(projectId);
      if (useAppStore.getState().versions.some((version) => version.id !== 'original')) {
        await loadFinalScript(projectId);
      }
      if (!cancelled) setProjectsChecked(true);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [fetchProjects, fetchResultVersions, loadFinalScript, projectId]);

  // ── Auto-start render on page load (no manual click needed) ──
  useEffect(() => {
    if (!projectsChecked || !projectId || !currentVersion || currentVersion.id === 'original') return;
    if (isExporting || outputUrl) return; // Already rendering or done
    const version = renderVersionMap[currentVersion.id] ?? 'original';
    const scriptVersion = currentVersion.id === 'original' ? undefined : currentVersion.id as FinalScriptStyle;
    void startRender(projectId, version, '1080p', scriptVersion);
  }, [projectsChecked, projectId, currentVersion?.id]);

  // Fetch waveform data
  useEffect(() => {
    if (!projectId) return;
    api.getWaveform(projectId).then((data) => {
      if (data?.data?.length) setWaveform(data);
    }).catch(() => {});
  }, [projectId]);

  // Visual trim handler
  const handleTrim = useCallback((segmentId: string, newDuration: number) => {
    // Update local state optimistically; the backend API call follows
    console.log(`Trim ${segmentId} to ${newDuration}s`);
    // Could call api.updateSegment(projectId, segmentId, { duration: newDuration })
  }, []);

  if ((!project || !currentVersion || !original) && !projectsChecked) return null;

  if (!project) {
    return <ErrorAlert title={'\u9879\u76ee\u4e0d\u5b58\u5728'} description={'\u8bf7\u56de\u5230\u9879\u76ee\u5217\u8868\u9009\u62e9\u6709\u6548\u9879\u76ee'} action={<Button onClick={() => navigate('/projects')}>{'\u8fd4\u56de\u9879\u76ee\u5217\u8868'}</Button>} />;
  }
  if (!currentVersion || !original) {
    return <ErrorAlert title={'\u65e0\u6cd5\u52a0\u8f7d\u8bc4\u4f30\u6570\u636e'} description={'\u8bf7\u5148\u751f\u6210\u811a\u672c\u6216\u91cd\u65b0\u5c1d\u8bd5'} />;
  }
  const description = currentScript
    ? `${project.name} ${'\u00b7'} ${scriptVersionLabel[currentScript.version] ?? currentScript.version}`
    : `${project.name} ${'\u00b7'} ${currentVersion.name}`;
  const renderedVideoUrl = outputUrl ? absoluteUrl(outputUrl) : null;
  const defaultRenderVersion = renderVersionMap[currentVersion.id] ?? 'original';
  const selectedScriptVersion = currentVersion.id === 'original' ? undefined : currentVersion.id as FinalScriptStyle;
  const structuralDecision = getStructuralDecision(currentScript);

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <WorkflowSteps current="result" projectId={projectId} />
      <SectionHeader
        title={copy.resultTitle}
        description={description}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{'\u5bfc\u51fa\u811a\u672c'}</Button>
            <Button variant="primary" onClick={() => setExportOpen(true)} disabled={structuralDecision?.renderBlocked}><Download className="h-4 w-4" />{copy.exportVideo}</Button>
          </div>
        }
      />

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <VersionTabs versions={versions} currentId={currentVersion.id} onChange={setVersion} />
        </div>
        {versions.length > 1 ? (
          <>
            <button
              type="button"
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${compareMode ? 'border-primary/40 bg-primary-muted text-primary' : 'border-border-visible text-text-secondary hover:border-primary/40 hover:text-primary'}`}
              onClick={() => setCompareMode(!compareMode)}
            >
              <Columns2 className="h-3.5 w-3.5" />
              对比
            </button>
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-lg border border-border-visible px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:border-primary/40 hover:text-primary"
              onClick={() => setHistoryOpen(true)}
            >
              <History className="h-3.5 w-3.5" />
              版本历史
            </button>
          </>
        ) : null}
      </div>

      {/* Version history side panel */}
      {historyOpen ? (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setHistoryOpen(false)} />
          <div className="relative z-10 flex h-full w-80 flex-col border-l border-border bg-card shadow-raised animate-in">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h3 className="font-semibold text-sm">版本历史</h3>
              <button onClick={() => setHistoryOpen(false)} className="rounded p-1 text-text-muted hover:text-text-primary">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {versions.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  className={`w-full rounded-lg border p-3 text-left transition-colors ${v.id === currentVersion.id ? 'border-primary/30 bg-primary-muted' : 'border-border-visible hover:border-primary/20'}`}
                  onClick={() => { setVersion(v.id); setHistoryOpen(false); }}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{v.name}</span>
                    <span className={`font-mono text-xs font-bold ${v.score >= 80 ? 'text-success' : v.score >= 65 ? 'text-warning' : 'text-text-muted'}`}>{v.score}</span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1 text-xs text-text-muted">
                    {v.metrics.scoreDelta !== 0 ? (
                      <span className={v.metrics.scoreDelta > 0 ? 'text-success' : 'text-error'}>
                        {v.metrics.scoreDelta > 0 ? '+' : ''}{v.metrics.scoreDelta} vs 基线
                      </span>
                    ) : null}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {/* Optimization score summary */}
      {currentVersion.id !== 'original' && currentVersion.metrics.scoreDelta !== 0 ? (
        <div className={`rounded-lg border px-4 py-3 shadow-sm ${currentVersion.metrics.scoreDelta > 0 ? 'border-success/40 bg-success/5' : 'border-warning/40 bg-warning/5'}`}>
          <p className="text-sm font-semibold">
            {currentVersion.metrics.scoreDelta > 0
              ? `AI \u4f18\u5316\u63d0\u5347 +${currentVersion.metrics.scoreDelta} \u5206`
              : `\u7efc\u5408\u8bc4\u5206 ${currentVersion.metrics.scoreDelta} \u5206`}
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            {currentVersion.metrics.scoreDelta > 0
              ? '\u4f18\u5316\u540e\u7684\u811a\u672c\u5728\u5f00\u5934\u5438\u5f15\u529b\u3001\u5356\u70b9\u8bc1\u660e\u529b\u548c\u8f6c\u5316\u53f7\u53ec\u529b\u65b9\u9762\u6709\u660e\u663e\u63d0\u5347'
              : '\u4f18\u5316\u540e\u7684\u811a\u672c\u8c03\u6574\u4e86\u7ed3\u6784\u548c\u6587\u6848\uff0c\u8bc4\u5206\u4e0e\u539f\u59cb\u89c6\u9891\u6301\u5e73\u6216\u7565\u6709\u5dee\u5f02'}
          </p>
        </div>
      ) : null}

      {/* AI qualitative review */}
      <AIReview data={currentScript?.metadata?.ai_review} />

      <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-text-secondary shadow-sm">
        <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent mr-2">\u89c4\u5219\u91cf\u5316\u5f97\u5206</span>
        {evaluationLabel}{'\uff1a'}{currentScript ? '\u5df2\u751f\u6210\u7248\u672c\u4e0e\u6837\u4f8b\u57fa\u7ebf\u4f7f\u7528\u540c\u4e00\u89c4\u5219\u8bc4\u5206\u3002' : '\u5c1a\u672a\u751f\u6210\u65b0\u811a\u672c\uff0c\u4ec5\u663e\u793a\u6837\u4f8b\u57fa\u7ebf\u3002'}
        <span className="block mt-1 text-xs text-text-muted">\u57fa\u4e8e\u53ef\u89e3\u91ca\u7684\u7206\u6b3e\u7279\u5f81\u516c\u5f0f\u81ea\u52a8\u8ba1\u7b97\uff0c\u7528\u4e8e\u9a71\u52a8\u7d20\u6750\u5339\u914d\u4e0e\u7f3a\u53e3\u8865\u5168\u51b3\u7b56</span>
      </div>
      {structuralDecision ? (
        <div className={`rounded-lg border bg-card px-4 py-3 shadow-sm ${structuralDecision.renderBlocked ? 'border-warning/40' : 'border-border'}`}>
          <div className="flex items-start gap-3">
            {structuralDecision.renderBlocked ? <ShieldAlert className="mt-0.5 h-5 w-5 flex-none text-warning" /> : <GitBranch className="mt-0.5 h-5 w-5 flex-none text-primary" />}
            <div>
              <p className="text-sm font-semibold text-text-primary">{structuralDecision.title}</p>
              <p className="mt-1 text-sm leading-6 text-text-secondary">{structuralDecision.description}</p>
            </div>
          </div>
        </div>
      ) : null}
      {compareMode && original ? (
        <div className="grid gap-5 lg:grid-cols-2 animate-in">
          <div className="space-y-4 rounded-lg border border-border-visible bg-card p-5">
            <h3 className="font-semibold text-sm text-text-muted">原始样例</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Metric label="综合分" value={original.score} />
              <Metric label="素材覆盖率" value={original.metrics.materialCoverage.after} />
              <Metric label="产品露出" value={original.metrics.productExposure.after} />
              <Metric label="CTA时长" value={original.metrics.ctaDuration.after} />
            </div>
            <CompareRadar original={original.health} current={original.health} />
          </div>
          <div className="space-y-4 rounded-lg border border-primary/20 bg-primary-muted p-5">
            <h3 className="font-semibold text-sm text-primary">{currentVersion.name}</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Metric label="综合分" value={currentVersion.score} />
              <Metric label="素材覆盖率" value={currentVersion.metrics.materialCoverage.after} />
              <Metric label="产品露出" value={currentVersion.metrics.productExposure.after} />
              <Metric label="CTA时长" value={currentVersion.metrics.ctaDuration.after} />
            </div>
            <CompareRadar original={original.health} current={currentVersion.health} />
          </div>
        </div>
      ) : (
      <>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
          <VideoPlayer
            timeline={currentVersion.timeline}
            src={renderedVideoUrl}
            onTimeUpdate={setPlaybackTime}
            isRendering={isExporting}
            renderProgress={renderProgress}
          />
          <aside className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="font-semibold">{'\u7248\u672c\u6307\u6807'}</h2>
              <span className="rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">\u89c4\u5219\u91cf\u5316</span>
            </div>
            <div className="mt-3">
              <MetricRow label={'\u7ed3\u6784\u5206'} before={`${original.score}`} after={`${currentVersion.score}`} delta={signedScore(currentVersion.metrics.scoreDelta)} positive={currentVersion.metrics.scoreDelta >= 0} />
              <MetricRow label={'\u7d20\u6750\u8986\u76d6\u7387'} {...currentVersion.metrics.materialCoverage} />
              <MetricRow label={'\u4ea7\u54c1\u9996\u6b21\u9732\u51fa'} {...currentVersion.metrics.productExposure} />
              <MetricRow label={'\u7f3a\u53e3\u6570\u91cf'} {...currentVersion.metrics.gapCount} />
              <MetricRow label={'CTA \u65f6\u957f'} {...currentVersion.metrics.ctaDuration} />
            </div>
          </aside>
        </div>
        <ResultTimeline
          segments={currentVersion.timeline}
          waveform={waveform}
          currentTime={playbackTime}
          onSeek={(t) => setPlaybackTime(t)}
          onTrim={handleTrim}
        />
        <TimelineSpecPreview spec={(currentScript?.metadata as Record<string, unknown>)?.timelineSpec as never ?? null} />
        <CompareRadar original={original.health} current={currentVersion.health} />
      </>
      )}
      <ExportDialog
        open={exportOpen}
        isExporting={isExporting}
        progress={renderProgress}
        outputUrl={renderedVideoUrl}
        script={currentScript}
        defaultVersion={defaultRenderVersion}
        renderDisabled={structuralDecision?.renderBlocked}
        renderDisabledReason={structuralDecision?.description}
        onClose={() => setExportOpen(false)}
        onExport={(version, resolution) => void startRender(projectId, version, resolution as RenderResolution, selectedScriptVersion)}
        onDownloadJson={() => currentScript && downloadJson(`${safeFileStem(project.name)}-${currentScript.version}-script.json`, currentScript)}
        onDownloadSrt={() => currentScript && downloadText(`${safeFileStem(project.name)}-${currentScript.version}.srt`, finalScriptToSrt(currentScript), 'text/plain;charset=utf-8')}
      />
    </section>
  );
}

function signedScore(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className="font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}

function absoluteUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE_URL}${path}`;
}

function getStructuralDecision(script: ReturnType<typeof useAppStore.getState>['currentScript']) {
  if (!script) return null;
  const reason = typeof script.metadata.edit_reason === 'string' ? script.metadata.edit_reason.trim() : '';
  const restructured = script.metadata.restructure_needed === true && reason.length > 0;
  const hasReorderedSegments = script.segments.some((segment) => segment.source === 'reorder');
  if (restructured) {
    return {
      title: '\u5df2\u5efa\u8bae\u91cd\u6784\u89c6\u9891\u7ed3\u6784',
      description: reason,
      renderBlocked: false,
    };
  }
  if (hasReorderedSegments) {
    return {
      title: '\u68c0\u6d4b\u5230\u672a\u6838\u9a8c\u7684\u7ed3\u6784\u91cd\u6392',
      description: '\u8be5\u811a\u672c\u751f\u6210\u4e8e\u7ed3\u6784\u51b3\u7b56\u8ffd\u8e2a\u542f\u7528\u524d\uff0c\u8bf7\u8fd4\u56de\u8fc1\u79fb\u53f0\u91cd\u65b0\u751f\u6210\u811a\u672c\u540e\u518d\u5bfc\u51fa\u89c6\u9891\u3002',
      renderBlocked: true,
    };
  }
  return {
    title: '\u4fdd\u6301\u539f\u89c6\u9891\u7ed3\u6784',
    description: reason || '\u5206\u6790\u672a\u63d0\u51fa\u53ef\u9a8c\u8bc1\u7684\u91cd\u6392\u4f9d\u636e\uff0c\u5df2\u4fdd\u7559\u539f\u5206\u955c\u987a\u5e8f\u4e0e\u65f6\u957f\u3002',
    renderBlocked: false,
  };
}
