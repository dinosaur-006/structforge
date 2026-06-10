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
import { WorkflowSteps } from '../components/layout/WorkflowSteps';

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

  if (isAnalyzing && !analysisResult) {
    return (
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
        <WorkflowSteps current="analyze" projectId={activeProjectId ?? projectId} />
        <SectionHeader title={copy.analyzeTitle} description={copy.analyzeSubtitle} />
        {isAnalyzing ? <AnalysisProgress progress={progress} stage={stage} /> : null}
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14 space-y-4">
      <WorkflowSteps current="analyze" projectId={activeProjectId ?? projectId} />
      <SectionHeader
        title={copy.analyzeTitle}
        description={copy.analyzeSubtitle}
        action={
          <Button variant="primary" onClick={goNext} disabled={!analysisResult}>
            {copy.nextStep}
            <MoveRight className="h-4 w-4" />
          </Button>
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
      {analysisSamples.length >= 2 ? (
        <SampleComparison samples={analysisSamples} onSelect={(jobId) => void selectReferenceSample(activeProjectId ?? projectId ?? '', jobId)} />
      ) : null}
      {analysisResult ? (
        <div className="space-y-4">
          {/* ── Analysis complete: prompt to continue ── */}
          <div className="flex items-center justify-between rounded-xl border border-success/30 bg-success/5 px-5 py-4">
            <div>
              <p className="font-semibold text-success">AI 分析完成</p>
              <p className="text-sm text-text-secondary">结构拆解、脚本提取、健康度评估已完成，点击继续进入 AI 自动优化</p>
            </div>
            <Button variant="primary" onClick={goNext}>
              {copy.nextStep}
              <MoveRight className="h-4 w-4" />
            </Button>
          </div>

          <VideoInfoCard structure={analysisResult} />
          <StructureTabs structure={analysisResult} jobId={analysisSamples[0]?.job_id} />
          <div className="flex justify-end">
            <button
              type="button"
              className="text-sm text-text-secondary underline underline-offset-2 hover:text-primary transition-colors"
              onClick={() => downloadJson(`${safeFileStem(currentProject?.name ?? 'structforge')}-analysis.json`, analysisResult)}
            >
              <Download className="mr-1 inline h-3.5 w-3.5" />
              导出结构 JSON
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
