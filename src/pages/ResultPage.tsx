import { Download } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CompareRadar } from '../components/result/CompareRadar';
import { ExportDialog } from '../components/result/ExportDialog';
import { ResultTimeline } from '../components/result/ResultTimeline';
import { VersionTabs } from '../components/result/VersionTabs';
import { VideoPlayer } from '../components/result/VideoPlayer';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';
import { MetricRow } from '../components/ui/MetricRow';
import { SectionHeader } from '../components/ui/SectionHeader';
import { copy } from '../shared/copy';
import type { FinalScriptStyle, RenderResolution, RenderVersion } from '../shared/types';
import { useAppStore } from '../store';

const scriptVersionLabel: Record<string, string> = {
  high_click: '\u9ad8\u70b9\u51fb\u7248',
  high_conversion: '\u9ad8\u8f6c\u5316\u7248',
  fast_pace: '\u5feb\u8282\u594f\u7248',
  high_quality: '\u9ad8\u8d28\u611f\u7248',
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
  const [projectsChecked, setProjectsChecked] = useState(false);
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
      await loadFinalScript(projectId);
      await fetchResultVersions(projectId);
      if (!cancelled) setProjectsChecked(true);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [fetchProjects, fetchResultVersions, loadFinalScript, projectId]);

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

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.resultTitle}
        description={description}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{copy.exportReport}</Button>
            <Button variant="primary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{copy.exportVideo}</Button>
          </div>
        }
      />

      <VersionTabs versions={versions} currentId={currentVersion.id} onChange={setVersion} />
      <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-text-secondary shadow-sm">
        {evaluationLabel}{'\uff1a'}{currentScript ? '\u5df2\u751f\u6210\u7248\u672c\u4e0e\u6837\u4f8b\u57fa\u7ebf\u4f7f\u7528\u540c\u4e00\u89c4\u5219\u8bc4\u5206\u3002' : '\u5c1a\u672a\u751f\u6210\u65b0\u811a\u672c\uff0c\u4ec5\u663e\u793a\u6837\u4f8b\u57fa\u7ebf\u3002'}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
        <VideoPlayer timeline={currentVersion.timeline} src={renderedVideoUrl} />
        <aside className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">{'\u7248\u672c\u6307\u6807'}</h2>
          <div className="mt-3">
            <MetricRow label={'\u7ed3\u6784\u5206'} before={`${original.score}`} after={`${currentVersion.score}`} delta={signedScore(currentVersion.metrics.scoreDelta)} positive={currentVersion.metrics.scoreDelta >= 0} />
            <MetricRow label={'\u7d20\u6750\u8986\u76d6\u7387'} {...currentVersion.metrics.materialCoverage} />
            <MetricRow label={'\u4ea7\u54c1\u9996\u6b21\u9732\u51fa'} {...currentVersion.metrics.productExposure} />
            <MetricRow label={'\u7f3a\u53e3\u6570\u91cf'} {...currentVersion.metrics.gapCount} />
            <MetricRow label={'CTA \u65f6\u957f'} {...currentVersion.metrics.ctaDuration} />
          </div>
        </aside>
      </div>
      <ResultTimeline segments={currentVersion.timeline} onSeek={() => undefined} />
      <CompareRadar original={original.health} current={currentVersion.health} />
      <ExportDialog
        open={exportOpen}
        isExporting={isExporting}
        progress={renderProgress}
        outputUrl={renderedVideoUrl}
        defaultVersion={defaultRenderVersion}
        onClose={() => setExportOpen(false)}
        onExport={(version: RenderVersion, resolution: RenderResolution) => void startRender(projectId, version, resolution, selectedScriptVersion)}
      />
    </section>
  );
}

function signedScore(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

function absoluteUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE_URL}${path}`;
}
