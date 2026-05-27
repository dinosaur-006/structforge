import { Download, MoveRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AnalysisProgress } from '../components/analyze/AnalysisProgress';
import { CapabilityStatusPanel } from '../components/analyze/CapabilityStatusPanel';
import { StructureTabs } from '../components/analyze/StructureTabs';
import { VideoInfoCard } from '../components/analyze/VideoInfoCard';
import { VideoUploader } from '../components/analyze/VideoUploader';
import { SampleComparison } from '../components/analyze/SampleComparison';
import { Button } from '../components/ui/Button';
import { SectionHeader } from '../components/ui/SectionHeader';
import { copy } from '../shared/copy';
import { downloadJson, safeFileStem } from '../shared/download';
import type { Capabilities } from '../shared/types';
import { api } from '../services/api';
import { useAppStore } from '../store';

export default function AnalyzePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') ?? undefined;
  const videoFile = useAppStore((state) => state.videoFile);
  const setVideoFile = useAppStore((state) => state.setVideoFile);
  const isAnalyzing = useAppStore((state) => state.isAnalyzing);
  const progress = useAppStore((state) => state.progress);
  const stage = useAppStore((state) => state.stage);
  const analysisResult = useAppStore((state) => state.analysisResult);
  const analysisSamples = useAppStore((state) => state.analysisSamples);
  const activeProjectId = useAppStore((state) => state.activeProjectId);
  const startAnalysis = useAppStore((state) => state.startAnalysis);
  const fetchAnalysisSamples = useAppStore((state) => state.fetchAnalysisSamples);
  const selectReferenceSample = useAppStore((state) => state.selectReferenceSample);
  const findProject = useAppStore((state) => state.findProject);
  const [selectedSamples, setSelectedSamples] = useState<File[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const currentProject = findProject(activeProjectId ?? projectId ?? '');

  useEffect(() => {
    let cancelled = false;
    api.getCapabilities()
      .then((value) => {
        if (!cancelled) setCapabilities(value);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (projectId) void fetchAnalysisSamples(projectId);
  }, [fetchAnalysisSamples, projectId]);

  const goNext = () => {
    const targetProjectId = activeProjectId ?? projectId;
    if (!targetProjectId) return;
    navigate(`/migrate/${targetProjectId}`);
  };

  const runSelectedAnalysis = async () => {
    const files = selectedSamples.length ? selectedSamples : videoFile ? [videoFile] : [];
    let targetProjectId = activeProjectId ?? projectId;
    for (const file of files) {
      setVideoFile(file);
      const completedProjectId = await startAnalysis(targetProjectId);
      if (!completedProjectId) return;
      targetProjectId = completedProjectId;
    }
    setSelectedSamples([]);
  };

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.analyzeTitle}
        description={copy.analyzeSubtitle}
        action={
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              disabled={!analysisResult}
              onClick={() => analysisResult && downloadJson(`${safeFileStem(currentProject?.name ?? 'structforge')}-analysis.json`, analysisResult)}
            >
              <Download className="h-4 w-4" />
              {copy.exportJson}
            </Button>
            <Button variant="primary" onClick={goNext} disabled={!analysisResult}>
              {copy.nextStep}
              <MoveRight className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      {capabilities ? <CapabilityStatusPanel capabilities={capabilities} /> : null}
      <VideoUploader
        file={videoFile}
        fileCount={selectedSamples.length || (videoFile ? 1 : 0)}
        onFile={setVideoFile}
        onFiles={setSelectedSamples}
        onStart={() => void runSelectedAnalysis()}
        disabled={isAnalyzing}
      />
      {isAnalyzing ? <AnalysisProgress progress={progress} stage={stage} /> : null}
      {analysisSamples.length ? (
        <SampleComparison samples={analysisSamples} onSelect={(jobId) => void selectReferenceSample(activeProjectId ?? projectId ?? '', jobId)} />
      ) : null}
      {analysisResult ? (
        <div className="space-y-5">
          <VideoInfoCard structure={analysisResult} />
          <StructureTabs structure={analysisResult} />
        </div>
      ) : null}
    </section>
  );
}
