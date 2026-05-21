import { Download } from 'lucide-react';
import { useMemo, useState } from 'react';
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
import { useAppStore } from '../store';

export default function ResultPage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const [exportOpen, setExportOpen] = useState(false);
  const findProject = useAppStore((state) => state.findProject);
  const project = findProject(projectId);
  const versions = useAppStore((state) => state.versions);
  const currentVersionId = useAppStore((state) => state.currentVersionId);
  const setVersion = useAppStore((state) => state.setVersion);
  const isExporting = useAppStore((state) => state.isExporting);
  const exportResult = useAppStore((state) => state.exportResult);
  const currentVersion = useMemo(() => versions.find((version) => version.id === currentVersionId) ?? versions[0], [currentVersionId, versions]);
  const original = versions[0];

  if (!project) {
    return <ErrorAlert title={'\u9879\u76ee\u4e0d\u5b58\u5728'} description={'\u8bf7\u56de\u5230\u9879\u76ee\u5217\u8868\u9009\u62e9\u6709\u6548\u9879\u76ee'} action={<Button onClick={() => navigate('/projects')}>{'\u8fd4\u56de\u9879\u76ee\u5217\u8868'}</Button>} />;
  }

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.resultTitle}
        description={`${project.name} ${'\u00b7'} ${currentVersion.name}`}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{copy.exportReport}</Button>
            <Button variant="primary" onClick={() => setExportOpen(true)}><Download className="h-4 w-4" />{copy.exportVideo}</Button>
          </div>
        }
      />

      <VersionTabs versions={versions} currentId={currentVersion.id} onChange={setVersion} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
        <VideoPlayer timeline={currentVersion.timeline} />
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
      <ResultTimeline segments={currentVersion.timeline} onSeek={() => undefined} />
      <CompareRadar original={original.health} current={currentVersion.health} />
      <ExportDialog open={exportOpen} isExporting={isExporting} onClose={() => setExportOpen(false)} onExport={() => void exportResult()} />
    </section>
  );
}
