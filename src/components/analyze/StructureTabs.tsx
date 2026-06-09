import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Tabs } from '../ui/Tabs';
import { Button } from '../ui/Button';
import type { VideoStructure } from '../../shared/types';
import { BurstAuditPanel } from './BurstAuditPanel';
import { HealthAssessment } from './HealthAssessment';
import { PackagingStructure } from './PackagingStructure';
import { RhythmStructure } from './RhythmStructure';
import { ScriptStructure } from './ScriptStructure';
import { useAppStore } from '../../store';

type AnalyzeTab = 'script' | 'rhythm' | 'packaging' | 'health' | 'audit';

const items = [
  { id: 'script' as const, label: '\u811a\u672c\u7ed3\u6784' },
  { id: 'rhythm' as const, label: '\u8282\u594f\u7ed3\u6784' },
  { id: 'packaging' as const, label: '\u5305\u88c5\u7ed3\u6784' },
  { id: 'health' as const, label: '\u5065\u5eb7\u5ea6' },
  { id: 'audit' as const, label: '\u7206\u6b3e\u5ba1\u8ba1' },
];

type AuditFetchState = 'idle' | 'loading' | 'loaded' | 'error';

export function StructureTabs({ structure, jobId }: { structure: VideoStructure; jobId?: string }) {
  const [tab, setTab] = useState<AnalyzeTab>('script');
  const [auditReport, setAuditReport] = useState<Record<string, unknown> | null>(null);
  const [auditState, setAuditState] = useState<AuditFetchState>('idle');
  const [auditError, setAuditError] = useState<string>('');
  const addToast = useAppStore((s) => s.addToast);

  const fetchAudit = useCallback(() => {
    if (!jobId) return;
    setAuditState('loading');
    setAuditError('');
    // Use the API base URL from the shared config, matching the api service pattern
    const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';
    fetch(`${API_BASE}/api/v1/audit/${jobId}`, { method: 'POST' })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail || `HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((data) => {
        setAuditReport(data);
        setAuditState('loaded');
      })
      .catch((err: Error) => {
        const msg = err.message || '\u5ba1\u8ba1\u8bf7\u6c42\u5931\u8d25';
        setAuditError(msg);
        setAuditState('error');
        addToast({ tone: 'error', title: '\u7206\u6b3e\u5ba1\u8ba1\u5931\u8d25', description: msg });
      });
  }, [jobId, addToast]);

  useEffect(() => {
    if (tab === 'audit' && jobId && auditState === 'idle') {
      fetchAudit();
    }
  }, [tab, jobId, auditState, fetchAudit]);

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <Tabs items={items} value={tab} onChange={setTab} />
      <div className="mt-5">
        {tab === 'script' ? <ScriptStructure segments={structure.script} /> : null}
        {tab === 'rhythm' ? <RhythmStructure data={structure.rhythm} /> : null}
        {tab === 'packaging' ? <PackagingStructure data={structure.packaging} /> : null}
        {tab === 'health' ? <HealthAssessment scores={structure.health} /> : null}
        {tab === 'audit' ? (
          auditState === 'loading' ? (
            <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card text-sm text-text-muted">
              <Loader2 className="h-8 w-8 animate-spin text-primary/60" />
              <span>\u6b63\u5728\u8ba1\u7b97 32 \u9879\u7206\u6b3e\u6307\u6807...</span>
              <span className="text-xs text-text-muted">\u5305\u542b LLM \u8f6f\u5206\u6790\uff0c\u53ef\u80fd\u9700\u8981 15-60 \u79d2</span>
            </div>
          ) : auditState === 'error' ? (
            <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-warning/30 bg-warning/5 px-6 text-center">
              <AlertTriangle className="h-8 w-8 text-warning" />
              <div>
                <p className="text-sm font-medium text-text-primary">\u5ba1\u8ba1\u8bf7\u6c42\u5931\u8d25</p>
                <p className="text-xs text-text-muted mt-1">{auditError}</p>
              </div>
              <Button variant="secondary" size="sm" onClick={fetchAudit}>
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                \u91cd\u8bd5
              </Button>
            </div>
          ) : (
            <BurstAuditPanel report={auditReport as never} />
          )
        ) : null}
      </div>
    </div>
  );
}
