import { useEffect, useState } from 'react';
import { Tabs } from '../ui/Tabs';
import type { VideoStructure } from '../../shared/types';
import { BurstAuditPanel } from './BurstAuditPanel';
import { HealthAssessment } from './HealthAssessment';
import { PackagingStructure } from './PackagingStructure';
import { RhythmStructure } from './RhythmStructure';
import { ScriptStructure } from './ScriptStructure';
import { api } from '../../services/api';

type AnalyzeTab = 'script' | 'rhythm' | 'packaging' | 'health' | 'audit';

const items = [
  { id: 'script' as const, label: '\u811a\u672c\u7ed3\u6784' },
  { id: 'rhythm' as const, label: '\u8282\u594f\u7ed3\u6784' },
  { id: 'packaging' as const, label: '\u5305\u88c5\u7ed3\u6784' },
  { id: 'health' as const, label: '\u5065\u5eb7\u5ea6' },
  { id: 'audit' as const, label: '\u7206\u6b3e\u5ba1\u8ba1' },
];

export function StructureTabs({ structure, jobId }: { structure: VideoStructure; jobId?: string }) {
  const [tab, setTab] = useState<AnalyzeTab>('script');
  const [auditReport, setAuditReport] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (tab === 'audit' && jobId && !auditReport) {
      // Fetch audit report when tab is selected
      fetch(`http://127.0.0.1:8000/api/v1/audit/${jobId}`, { method: 'POST' })
        .then((r) => r.json())
        .then((data) => setAuditReport(data))
        .catch(() => setAuditReport(null));
    }
  }, [tab, jobId, auditReport]);

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <Tabs items={items} value={tab} onChange={setTab} />
      <div className="mt-5">
        {tab === 'script' ? <ScriptStructure segments={structure.script} /> : null}
        {tab === 'rhythm' ? <RhythmStructure data={structure.rhythm} /> : null}
        {tab === 'packaging' ? <PackagingStructure data={structure.packaging} /> : null}
        {tab === 'health' ? <HealthAssessment scores={structure.health} /> : null}
        {tab === 'audit' ? <BurstAuditPanel report={auditReport as never} /> : null}
      </div>
    </div>
  );
}
