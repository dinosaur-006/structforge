import { Download, MoveRight } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AnalysisProgress } from '../components/analyze/AnalysisProgress';
import { StructureTabs } from '../components/analyze/StructureTabs';
import { VideoInfoCard } from '../components/analyze/VideoInfoCard';
import { VideoUploader } from '../components/analyze/VideoUploader';
import { Button } from '../components/ui/Button';
import { SectionHeader } from '../components/ui/SectionHeader';
import { copy } from '../shared/copy';
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
  const activeProjectId = useAppStore((state) => state.activeProjectId);
  const startAnalysis = useAppStore((state) => state.startAnalysis);
  const addToast = useAppStore((state) => state.addToast);

  const goNext = () => {
    const targetProjectId = activeProjectId ?? projectId;
    if (!targetProjectId) return;
    navigate(`/migrate/${targetProjectId}`);
  };

  return (
    <section className="mx-auto max-w-[1240px] space-y-6">
      <SectionHeader
        title={copy.analyzeTitle}
        description={copy.analyzeSubtitle}
        action={
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => addToast({ tone: 'info', title: copy.exportJson, description: '\u5df2\u751f\u6210\u6a21\u62df JSON' })}>
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

      <VideoUploader file={videoFile} onFile={setVideoFile} onStart={() => void startAnalysis(projectId)} disabled={isAnalyzing} />
      {isAnalyzing ? <AnalysisProgress progress={progress} stage={stage} /> : null}
      {analysisResult ? (
        <div className="space-y-5">
          <VideoInfoCard structure={analysisResult} />
          <StructureTabs structure={analysisResult} />
        </div>
      ) : null}
    </section>
  );
}
