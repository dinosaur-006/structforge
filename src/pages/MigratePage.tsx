import { Redo2, RotateCcw, Save, Undo2, WandSparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AssetPanel } from '../components/migrate/AssetPanel';
import { GapPanel } from '../components/migrate/GapPanel';
import { SegmentDrawer } from '../components/migrate/SegmentDrawer';
import { TimelineEditor } from '../components/migrate/TimelineEditor';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';
import { SectionHeader } from '../components/ui/SectionHeader';
import { copy } from '../shared/copy';
import { useAppStore } from '../store';

export default function MigratePage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const [style, setStyle] = useState('fast');
  const [structureChecked, setStructureChecked] = useState(false);
  const fetchProjects = useAppStore((state) => state.fetchProjects);
  const routeLoading = useAppStore((state) => state.routeLoading);
  const findProject = useAppStore((state) => state.findProject);
  const project = findProject(projectId);
  const loadProjectStructure = useAppStore((state) => state.loadProjectStructure);
  const currentStructure = useAppStore((state) => state.currentStructure);
  const assets = useAppStore((state) => state.assets);
  const assetLoading = useAppStore((state) => state.assetLoading);
  const gaps = useAppStore((state) => state.gaps);
  const selectedSegmentId = useAppStore((state) => state.selectedSegmentId);
  const drawerOpen = useAppStore((state) => state.drawerOpen);
  const isFixing = useAppStore((state) => state.isFixing);
  const selectSegment = useAppStore((state) => state.selectSegment);
  const setDrawerOpen = useAppStore((state) => state.setDrawerOpen);
  const updateSegment = useAppStore((state) => state.updateSegment);
  const reorderSegments = useAppStore((state) => state.reorderSegments);
  const undo = useAppStore((state) => state.undo);
  const redo = useAppStore((state) => state.redo);
  const resetStructure = useAppStore((state) => state.resetStructure);
  const fixGaps = useAppStore((state) => state.fixGaps);
  const fixGap = useAppStore((state) => state.fixGap);
  const addToast = useAppStore((state) => state.addToast);
  const removeSelectedSegment = useAppStore((state) => state.removeSelectedSegment);
  const uploadAsset = useAppStore((state) => state.uploadAsset);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!projectId) return;
      setStructureChecked(false);
      if (!useAppStore.getState().projects.length) await fetchProjects();
      try {
        await loadProjectStructure(projectId);
      } catch {
        // Store owns toast/error state. The page switches to the missing-project alert below.
      } finally {
        if (!cancelled) setStructureChecked(true);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [fetchProjects, loadProjectStructure, projectId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        void redo();
      } else if (event.ctrlKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        void undo();
      } else if (event.key === 'Delete') {
        void removeSelectedSegment();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [redo, removeSelectedSegment, undo]);

  const selectedSegment = useMemo(
    () => currentStructure?.script.find((segment) => segment.id === selectedSegmentId) ?? null,
    [currentStructure, selectedSegmentId],
  );

  if (!currentStructure && !structureChecked && routeLoading) return null;

  if (!currentStructure && structureChecked) {
    return <ErrorAlert title={'\u9879\u76ee\u4e0d\u5b58\u5728'} description={'\u8bf7\u56de\u5230\u9879\u76ee\u5217\u8868\u9009\u62e9\u6709\u6548\u9879\u76ee'} action={<Button onClick={() => navigate('/projects')}>{'\u8fd4\u56de\u9879\u76ee\u5217\u8868'}</Button>} />;
  }

  if (!currentStructure) return null;

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.migrateTitle}
        description={`${'\u9879\u76ee\uff1a'}${project?.name ?? projectId}`}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => navigate(`/result/${projectId}`)}>{copy.previewResult}</Button>
            <Button variant="primary" onClick={() => navigate(`/result/${projectId}`)}>{copy.generateVideo}</Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-3 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => addToast({ tone: 'success', title: '\u4fdd\u5b58\u6210\u529f' })}><Save className="h-4 w-4" />{'\u4fdd\u5b58'}</Button>
          <Button variant="ghost" onClick={() => void undo()}><Undo2 className="h-4 w-4" />{'\u64a4\u9500'}</Button>
          <Button variant="ghost" onClick={() => void redo()}><Redo2 className="h-4 w-4" />{'\u91cd\u505a'}</Button>
          <Button variant="ghost" onClick={() => void resetStructure()}><RotateCcw className="h-4 w-4" />{'\u91cd\u7f6e'}</Button>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <WandSparkles className="h-4 w-4 text-primary" />
          {'\u98ce\u683c'}
          <select value={style} onChange={(event) => setStyle(event.target.value)} className="h-10 rounded-lg border border-border bg-card px-3 text-text-primary outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option value="fast">{'\u5feb\u8282\u594f'}</option>
            <option value="conversion">{'\u9ad8\u8f6c\u5316'}</option>
            <option value="premium">{'\u9ad8\u8d28\u611f'}</option>
          </select>
        </label>
      </div>

      <div className="grid gap-5 lg:grid-cols-[16rem,1fr]">
        <AssetPanel assets={assets} assetLoading={assetLoading} onUploadAsset={(file) => void uploadAsset(file)} />
        <TimelineEditor segments={currentStructure.script} gaps={gaps} onSelect={selectSegment} onReorder={(activeId, overId) => void reorderSegments(activeId, overId)} />
      </div>
      <GapPanel gaps={gaps} isFixing={isFixing} onFixAll={() => void fixGaps()} onFixGap={(gapId, strategy) => void fixGap(gapId, strategy)} />
      <SegmentDrawer open={drawerOpen} segment={selectedSegment} assets={assets} onClose={() => setDrawerOpen(false)} onApply={(id, changes) => void updateSegment(id, changes)} />
    </section>
  );
}
