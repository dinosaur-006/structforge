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
import type { FinalScript, ResultTimelineSegment } from '../shared/types';
import { useAppStore } from '../store';

const scriptVersionLabel: Record<string, string> = {
  high_click: '\u9ad8\u70b9\u51fb\u7248',
  high_conversion: '\u9ad8\u8f6c\u5316\u7248',
  fast_pace: '\u5feb\u8282\u594f\u7248',
  high_quality: '\u9ad8\u8d28\u611f\u7248',
  default: '\u9ed8\u8ba4\u7248',
};

export default function ResultPage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const [exportOpen, setExportOpen] = useState(false);
  const [projectsChecked, setProjectsChecked] = useState(false);
  const fetchProjects = useAppStore((state) => state.fetchProjects);
  const loadFinalScript = useAppStore((state) => state.loadFinalScript);
  const findProject = useAppStore((state) => state.findProject);
  const project = findProject(projectId);
  const currentScript = useAppStore((state) => state.currentScript);
  const versions = useAppStore((state) => state.versions);
  const currentVersionId = useAppStore((state) => state.currentVersionId);
  const setVersion = useAppStore((state) => state.setVersion);
  const isExporting = useAppStore((state) => state.isExporting);
  const exportResult = useAppStore((state) => state.exportResult);
  const currentVersion = useMemo(() => versions.find((version) => version.id === currentVersionId) ?? versions[0], [currentVersionId, versions]);
  const original = versions[0];
  const scriptTimeline = useMemo(() => (currentScript ? timelineFromScript(currentScript) : null), [currentScript]);
  const activeTimeline = scriptTimeline ?? currentVersion.timeline;
  const description = currentScript
    ? `${project?.name ?? projectId} ${'\u00b7'} ${scriptVersionLabel[currentScript.version] ?? currentScript.version}`
    : `${project?.name ?? projectId} ${'\u00b7'} ${currentVersion.name}`;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!useAppStore.getState().projects.length) await fetchProjects();
      await loadFinalScript(projectId);
      if (!cancelled) setProjectsChecked(true);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [fetchProjects, loadFinalScript, projectId]);

  if (!project && !projectsChecked) return null;

  if (!project) {
    return <ErrorAlert title={'\u9879\u76ee\u4e0d\u5b58\u5728'} description={'\u8bf7\u56de\u5230\u9879\u76ee\u5217\u8868\u9009\u62e9\u6709\u6548\u9879\u76ee'} action={<Button onClick={() => navigate('/projects')}>{'\u8fd4\u56de\u9879\u76ee\u5217\u8868'}</Button>} />;
  }

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
      {!currentScript ? (
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-text-secondary shadow-sm">
          {'\u5c1a\u672a\u751f\u6210\u6700\u7ec8\u811a\u672c\uff0c\u5f53\u524d\u663e\u793a\u6f14\u793a\u7248\u672c\u6570\u636e\u3002'}
        </div>
      ) : null}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
        <VideoPlayer timeline={activeTimeline} />
        <aside className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">{'\u7248\u672c\u6307\u6807'}</h2>
          <div className="mt-3">
            <MetricRow label={'\u7ed3\u6784\u5206'} before={`${original.score}`} after={`${currentVersion.score}`} delta={`+${currentVersion.metrics.scoreDelta}`} />
            <MetricRow label={'Hook \u63d0\u524d'} before={'0s'} after={currentVersion.metrics.hookAdvance} delta={currentVersion.metrics.hookAdvance} />
            <MetricRow label={'\u4ea7\u54c1\u9732\u51fa'} before={'0s'} after={currentVersion.metrics.exposureAdvance} delta={currentVersion.metrics.exposureAdvance} />
            <MetricRow label={'\u65e0\u6548\u7247\u6bb5'} before={'0%'} after={currentVersion.metrics.wasteReduction} delta={currentVersion.metrics.wasteReduction} />
            <MetricRow label={'CTA \u5f3a\u5316'} before={'0s'} after={currentVersion.metrics.ctaDuration} delta={currentVersion.metrics.ctaDuration} />
          </div>
        </aside>
      </div>
      <ResultTimeline segments={activeTimeline} onSeek={() => undefined} />
      <CompareRadar original={original.health} current={currentVersion.health} />
      <ExportDialog open={exportOpen} isExporting={isExporting} onClose={() => setExportOpen(false)} onExport={() => void exportResult()} />
    </section>
  );
}

function timelineFromScript(script: FinalScript): ResultTimelineSegment[] {
  return script.segments.map((segment) => ({
    id: segment.id,
    label: segment.script,
    start: segment.start,
    end: segment.end,
    source: segment.asset_id ? 'original' : 'packaging',
  }));
}
