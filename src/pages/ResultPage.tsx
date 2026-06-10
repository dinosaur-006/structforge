import { Columns2, Download, FileText, GitBranch, History, ShieldAlert, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AIReview } from '../components/result/AIReview';
import { ExportDialog } from '../components/result/ExportDialog';
import { PayloadPreviewDrawer } from '../components/result/PayloadPreviewDrawer';
import { ResultTimeline } from '../components/result/ResultTimeline';
import { ReviewPanel } from '../components/result/ReviewPanel';
import { VersionTabs } from '../components/result/VersionTabs';
import { VideoPlayer } from '../components/result/VideoPlayer';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';
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
  const [segmentModes, setSegmentModes] = useState<Record<string, 'image' | 'video'>>({});
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
  const renderStage = useAppStore((state) => state.renderStage);
  const renderWarnings = useAppStore((state) => state.renderWarnings);
  const outputUrl = useAppStore((state) => state.outputUrl);
  const startRender = useAppStore((state) => state.startRender);
  const currentVersion = useMemo(() => versions.find((version) => version.id === currentVersionId) ?? versions[0], [currentVersionId, versions]);
  const original = versions[0];
  // Blueprint / Pre-viz state
  const [blueprintOpen, setBlueprintOpen] = useState(false);
  const apiCapabilities = useAppStore((state) => state.apiCapabilities);
  const blueprintPayloads = useAppStore((state) => state.blueprintPayloads);
  const blueprintLoading = useAppStore((state) => state.blueprintLoading);
  const selectedBlueprintId = useAppStore((state) => state.selectedBlueprintId);
  const fetchCapabilities = useAppStore((state) => state.fetchCapabilities);
  const fetchBlueprintPayloads = useAppStore((state) => state.fetchBlueprintPayloads);
  const selectBlueprint = useAppStore((state) => state.selectBlueprint);
  const hasDraftSegments = useMemo(() => {
    // Check timeline for already-marked draft sources
    const draftSources = new Set(['aigc_draft', 'aigc', 'packaging']);
    if (currentVersion?.timeline?.some((seg) => draftSources.has(seg.source))) return true;
    // Or: FinalScript has segments without assets
    if (currentScript?.segments?.some((seg) => !seg.asset_id)) return true;
    return false;
  }, [currentVersion?.timeline, currentScript?.segments]);

  // Auto-generate timeline spec from script segments when LLM data is missing
  const timelineSpec = useMemo(() => {
    const llmSpec = (currentScript?.metadata as Record<string, unknown>)?.timelineSpec;
    if (llmSpec) return llmSpec;
    if (!currentScript) return null;
    const fps = 30;
    const totalFrames = Math.round(currentScript.total_duration * fps);
    return {
      composition: { fps, width: 1080, height: 1920, totalFrames, durationSeconds: currentScript.total_duration },
      tracks: [
        { id: 'video-track', type: 'video', label: '视频', clips: currentScript.segments.map((seg, i) => ({
          id: `clip-${i}`, startFrame: Math.round(seg.start * fps), durationInFrames: Math.round(seg.duration * fps),
          component: seg.type === 'hook' ? 'TitleCard' : seg.type === 'cta' ? 'CTACard' : seg.type === 'product' ? 'ProductHero' : 'OverlayText',
          props: { label: seg.type, script: seg.script?.slice(0, 30) || '' },
        }))},
        { id: 'subtitle-track', type: 'subtitle', label: '字幕', clips: currentScript.segments.map((seg, i) => ({
          id: `s-${i}`, startFrame: Math.round(seg.start * fps), durationInFrames: Math.round(seg.duration * fps),
          component: 'OverlayText', props: { text: seg.script?.slice(0, 40) || '' },
        }))},
      ],
    };
  }, [currentScript]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      // Restore render error from previous session if page was refreshed
      try {
        const stored = sessionStorage.getItem('lastRenderError');
        if (stored && !useAppStore.getState().renderError) {
          const parsed = JSON.parse(stored);
          useAppStore.setState({ renderError: parsed.error, renderStatus: 'failed' as const });
        }
      } catch {}

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

  // ── Render on demand ──
  const triggerRender = useCallback(() => {
    if (!projectId || !currentVersion || currentVersion.id === 'original') return;
    const version = renderVersionMap[currentVersion.id] ?? 'original';
    const scriptVersion = currentVersion.id === 'original' ? undefined : currentVersion.id as FinalScriptStyle;
    const modes: Record<string, string> = {};
    currentScript?.segments.forEach(s => { modes[s.id] = segmentModes[s.id] || 'image'; });
    void startRender(projectId, version, '1080p', scriptVersion, modes);
  }, [projectId, currentVersion?.id, currentScript?.segments, segmentModes, startRender]);

  // Fetch waveform data
  useEffect(() => {
    if (!projectId) return;
    api.getWaveform(projectId).then((data) => {
      if (data?.data?.length) setWaveform(data);
    }).catch(() => {});
  }, [projectId]);

  // Auto-close ExportDialog when render completes and video is ready
  useEffect(() => {
    if (outputUrl && !isExporting && exportOpen) {
      setExportOpen(false);
    }
  }, [outputUrl, isExporting, exportOpen]);

  // Fallback: if render completed but no outputUrl in store, fetch it directly
  const renderJobId = useAppStore((s) => s.renderJobId);
  const renderStatus = useAppStore((s) => s.renderStatus);
  useEffect(() => {
    if (renderStatus === 'completed' && !outputUrl && renderJobId) {
      api.getRenderJob(renderJobId).then((s) => {
        if (s.output_url) {
          useAppStore.setState({ outputUrl: s.output_url });
        }
      }).catch(() => {});
    }
  }, [renderStatus, outputUrl, renderJobId]);

  // Fetch capabilities and blueprint payloads on mount
  useEffect(() => {
    if (!projectId) return;
    void fetchCapabilities();
    void fetchBlueprintPayloads(projectId);
  }, [fetchCapabilities, fetchBlueprintPayloads, projectId]);

  // Handle blueprint drawer open: select first draft segment
  const handleBlueprintClick = useCallback(() => {
    const draftSeg = currentVersion?.timeline?.find((s) => s.source === 'aigc_draft');
    if (draftSeg) {
      selectBlueprint(draftSeg.id);
    }
    setBlueprintOpen(true);
  }, [currentVersion?.timeline, selectBlueprint]);

  // Handle clicking a draft segment in the timeline
  const handleTimelineSeek = useCallback(
    (t: number) => {
      setPlaybackTime(t);
      // If seeking to a draft segment, show its payload
      const segAtTime = currentVersion?.timeline?.find(
        (s) => s.start <= t && s.end >= t && s.source === 'aigc_draft',
      );
      if (segAtTime) {
        selectBlueprint(segAtTime.id);
        setBlueprintOpen(true);
      }
    },
    [currentVersion?.timeline, selectBlueprint],
  );

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
    <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
      <WorkflowSteps current="result" projectId={projectId} />
      <SectionHeader
        title={copy.resultTitle}
        description={description}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{'\u5bfc\u51fa\u811a\u672c'}</Button>
            <Button variant="primary" onClick={() => setExportOpen(true)} disabled={structuralDecision?.renderBlocked}><Download className="h-4 w-4" />{copy.exportVideo}</Button>
            {hasDraftSegments && (() => {
                const drafts = currentScript?.segments?.filter(s => !s.asset_id) ?? [];
                const count = drafts.length;
                const doExport = () => {
                  const lines: string[] = [];
                  lines.push('# StructForge AI \u89c6\u9891\u751f\u6210\u63d0\u793a\u8bcd');
                  lines.push(`# \u9879\u76ee: ${project.name}`);
                  lines.push(`# \u751f\u6210\u65f6\u95f4: ${new Date().toISOString()}`);
                  lines.push(`# \u5171 ${count} \u4e2a\u5206\u955c\u9700\u8981 AI \u751f\u6210`);
                  lines.push('# \u517c\u5bb9\u5e73\u53f0: RunningHub ComfyUI Flux');
                  lines.push('');
                  drafts.forEach((seg, i) => {
                    const label = seg.type?.toUpperCase() ?? `SEG-${i}`;
                    lines.push(`## ${i + 1}. ${label} (${seg.duration?.toFixed(1)}s)`);
                    lines.push(`\u5b57\u5e55: ${seg.script || '(\u65e0)'}`);
                    lines.push(`\u8fd0\u955c: ${(seg as Record<string, unknown>).camera || '\u9759\u6001'} | \u7279\u6548: ${(seg as Record<string, unknown>).visual_fx || '\u65e0'}`);
                    lines.push('');
                    lines.push('[Flux]');
                    lines.push(`\u7ad6\u5c4f\u77ed\u89c6\u9891\u753b\u9762\uff0c9:16\u6784\u56fe\uff0c\u7535\u5546\u5e26\u8d27\u98ce\u683c\u3002${seg.visual || seg.script || ''}`);
                    lines.push('');
                    
                    
                    lines.push('---');
                    lines.push('');
                  });
                  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = `structforge-prompts-${safeFileStem(project.name)}.txt`;
                  a.click(); URL.revokeObjectURL(url);
                };
                return (
                  <Button variant="primary" className="bg-[#C8843C] hover:bg-[#B07530] text-[#1C1C1E] border-0 font-bold text-sm" onClick={doExport}>
                    <FileText className="h-4 w-4" />
                    Export AI Prompts ({count} segments)
                  </Button>
                );
              })()}
          </div>
        }
      />

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <VersionTabs versions={(() => { const gen = versions.filter(v => v.id !== 'original'); return gen.length > 0 ? gen : versions; })()} currentId={currentVersion.id} onChange={setVersion} />
        </div>
        {versions.length > 1 ? (
          <>
            <button
              type="button"
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${compareMode ? 'border-primary/40 bg-primary-muted text-primary' : 'border-border-visible text-text-secondary hover:border-primary/40 hover:text-primary'}`}
              onClick={() => setCompareMode(!compareMode)}
            >
              <Columns2 className="h-3.5 w-3.5" />
              对比
            </button>
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-xl border border-border-visible px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:border-primary/40 hover:text-primary"
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
          <div className="relative z-10 flex h-full w-80 flex-col border-l border-border/60 bg-white shadow-raised animate-in">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
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
                  className={`w-full rounded-xl border p-3 text-left transition-colors ${v.id === currentVersion.id ? 'border-primary/30 bg-primary-muted' : 'border-border-visible hover:border-primary/20'}`}
                  onClick={() => { setVersion(v.id); setHistoryOpen(false); }}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{v.name}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {/* Structural comparison summary */}
      {currentVersion.id !== 'original' && currentScript ? (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <span>{currentScript.segments.length} \u4e2a\u5206\u955c \u00b7 {currentScript.total_duration.toFixed(1)}s \u00b7 {scriptVersionLabel[currentScript.version] ?? currentScript.version}</span>
        </div>
      ) : null}

      {/* AI qualitative review */}
      <AIReview data={currentScript?.metadata?.ai_review} />

      {/* Render quality (self-audit) */}
      {(() => {
        const meta = currentScript?.metadata as Record<string, any> | undefined;
        const audit = meta?.self_audit;
        if (!audit?.visual_generation) return null;
        const vg = audit.visual_generation;
        const ag = audit.audio_generation;
        return (
          <div className="rounded-xl border border-border/60 bg-white px-4 py-3 text-sm shadow-sm">
            <span className="text-xs font-semibold text-text-primary">\u6e32\u67d3\u8d28\u91cf</span>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
              <div className="flex justify-between"><span className="text-xs text-text-muted">\u753b\u9762\u751f\u6210</span><span className="text-xs font-medium text-text-primary">{vg.method}</span></div>
              <div className="flex justify-between"><span className="text-xs text-text-muted">\u753b\u9762\u8d28\u91cf</span><span className="text-xs font-medium">{vg.quality}</span></div>
              <div className="flex justify-between"><span className="text-xs text-text-muted">AI \u751f\u56fe</span><span className="text-xs font-medium text-text-primary">{vg.flux_segments}/{audit.segment_count} \u6bb5</span></div>
              <div className="flex justify-between"><span className="text-xs text-text-muted">\u914d\u97f3</span><span className="text-xs font-medium text-text-primary">{ag?.method || '\u672a\u542f\u7528'}</span></div>
            </div>
          </div>
        );
      })()}

      {structuralDecision ? (
        <div className={`rounded-xl border bg-white px-4 py-3 shadow-sm ${structuralDecision.renderBlocked ? 'border-warning/40' : 'border-border'}`}>
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
          <div className="space-y-4 rounded-xl border border-border-visible bg-white p-5">
            <h3 className="font-semibold text-sm text-text-muted">原始样例</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Metric label="综合分" value={original.score} />
              <Metric label="素材覆盖率" value={original.metrics.materialCoverage.after} />
              <Metric label="产品露出" value={original.metrics.productExposure.after} />
              <Metric label="CTA时长" value={original.metrics.ctaDuration.after} />
            </div>
            
          </div>
          <div className="space-y-4 rounded-xl border border-primary/20 bg-primary-muted p-5">
            <h3 className="font-semibold text-sm text-primary">{currentVersion.name}</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Metric label="综合分" value={currentVersion.score} />
              <Metric label="素材覆盖率" value={currentVersion.metrics.materialCoverage.after} />
              <Metric label="产品露出" value={currentVersion.metrics.productExposure.after} />
              <Metric label="CTA时长" value={currentVersion.metrics.ctaDuration.after} />
            </div>
            
          </div>
        </div>
      ) : (
      <>
        {/* ── Review section: shown before render starts ── */}
        {currentScript && (() => {
          const meta = currentScript.metadata as Record<string, any> | undefined;
          const promptList = meta?.prompts as Array<{segment_id: string; prompt: string}> | undefined;
          const promptMap: Record<string, string> = {};
          if (promptList) { promptList.forEach(p => { promptMap[p.segment_id] = p.prompt; }); }
          return (
            <ReviewPanel
              segments={currentScript.segments}
              projectName={project.name}
              segmentModes={segmentModes}
              segmentPrompts={promptMap}
              onModeChange={(id, mode) => setSegmentModes(prev => ({ ...prev, [id]: mode }))}
              onGenerate={triggerRender}
              isRendering={isExporting}
            />
          );
        })()}

        <div className="grid gap-5">
          <VideoPlayer
            timeline={currentVersion.timeline}
            src={renderedVideoUrl}
            onTimeUpdate={setPlaybackTime}
            isRendering={isExporting}
            renderProgress={renderProgress}
            renderWarnings={renderWarnings}
            hasDraftSegments={hasDraftSegments}
            onBlueprintClick={handleBlueprintClick}
          />

        </div>
        <ResultTimeline
          segments={currentVersion.timeline}
          waveform={waveform}
          currentTime={playbackTime}
          onSeek={handleTimelineSeek}
          onTrim={handleTrim}
        />
        
        
      </>
      )}
      <ExportDialog
        open={exportOpen}
        isExporting={isExporting}
        progress={renderProgress}
        renderStage={renderStage}
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
      <PayloadPreviewDrawer
        open={blueprintOpen}
        onClose={() => setBlueprintOpen(false)}
        payloads={blueprintPayloads}
        loading={blueprintLoading}
        selectedSegmentId={selectedBlueprintId}
        videoGenAvailable={apiCapabilities.videoGen}
        isRendering={isExporting}
        onRenderRequest={() => {
          if (currentVersion?.id === 'original') return;
          const version = renderVersionMap[currentVersion?.id] ?? 'original';
          const scriptVersion = currentVersion?.id === 'original' ? undefined : currentVersion.id as FinalScriptStyle;
          void startRender(projectId, version, '1080p', scriptVersion);
        }}
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
