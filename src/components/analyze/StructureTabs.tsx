import { useState } from 'react';
import { Tabs } from '../ui/Tabs';
import type { VideoStructure } from '../../shared/types';
import { HealthAssessment } from './HealthAssessment';
import { PackagingStructure } from './PackagingStructure';
import { RhythmStructure } from './RhythmStructure';
import { ScriptStructure } from './ScriptStructure';

type AnalyzeTab = 'script' | 'rhythm' | 'packaging' | 'health';

const items = [
  { id: 'script' as const, label: '\u811a\u672c\u7ed3\u6784' },
  { id: 'rhythm' as const, label: '\u8282\u594f\u7ed3\u6784' },
  { id: 'packaging' as const, label: '\u5305\u88c5\u7ed3\u6784' },
  { id: 'health' as const, label: '\u5065\u5eb7\u5ea6' },
];

export function StructureTabs({ structure }: { structure: VideoStructure }) {
  const [tab, setTab] = useState<AnalyzeTab>('script');
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <Tabs items={items} value={tab} onChange={setTab} />
      <div className="mt-5">
        {tab === 'script' ? <ScriptStructure segments={structure.script} /> : null}
        {tab === 'rhythm' ? <RhythmStructure data={structure.rhythm} /> : null}
        {tab === 'packaging' ? <PackagingStructure data={structure.packaging} /> : null}
        {tab === 'health' ? <HealthAssessment scores={structure.health} /> : null}
      </div>
    </div>
  );
}
