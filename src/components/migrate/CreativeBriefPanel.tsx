import { useEffect, useState } from 'react';
import { FilePenLine } from 'lucide-react';
import type { ProjectBrief } from '../../shared/types';
import { Button } from '../ui/Button';

const emptyBrief: ProjectBrief = {
  productName: '',
  sellingPoints: [],
  targetAudience: '',
  offer: '',
  tone: '',
  mandatoryClaims: [],
};

export function CreativeBriefPanel({ brief, onSave }: { brief?: ProjectBrief; onSave: (brief: ProjectBrief) => Promise<void> | void }) {
  const [draft, setDraft] = useState<ProjectBrief>(brief ?? emptyBrief);
  const [sellingPoints, setSellingPoints] = useState((brief?.sellingPoints ?? []).join('\n'));
  const [mandatoryClaims, setMandatoryClaims] = useState((brief?.mandatoryClaims ?? []).join('\n'));

  useEffect(() => {
    const next = brief ?? emptyBrief;
    setDraft(next);
    setSellingPoints(next.sellingPoints.join('\n'));
    setMandatoryClaims(next.mandatoryClaims.join('\n'));
  }, [brief]);

  const save = () => {
    void onSave({
      ...draft,
      sellingPoints: lines(sellingPoints),
      mandatoryClaims: lines(mandatoryClaims),
    });
  };

  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FilePenLine className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">{'\u521b\u4f5c\u7b80\u62a5'}</h2>
        </div>
        <Button size="sm" variant="secondary" onClick={save}>{'\u4fdd\u5b58\u7b80\u62a5'}</Button>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label={'\u5546\u54c1\u540d\u79f0'} value={draft.productName} onChange={(value) => setDraft({ ...draft, productName: value })} />
        <Field label={'\u76ee\u6807\u4eba\u7fa4'} value={draft.targetAudience} onChange={(value) => setDraft({ ...draft, targetAudience: value })} />
        <Field label={'\u4f18\u60e0\u4fe1\u606f'} value={draft.offer} onChange={(value) => setDraft({ ...draft, offer: value })} />
        <Area label={'\u6838\u5fc3\u5356\u70b9'} value={sellingPoints} onChange={setSellingPoints} />
        <Area label={'\u5fc5\u5907\u58f0\u660e'} value={mandatoryClaims} onChange={setMandatoryClaims} />
        <Field label={'\u8868\u8fbe\u8bed\u6c14'} value={draft.tone} onChange={(value) => setDraft({ ...draft, tone: value })} />
      </div>
    </section>
  );
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-text-secondary">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-text-primary outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}

function Area({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-text-secondary">
      {label}
      <textarea
        value={value}
        placeholder={'\u6bcf\u884c\u4e00\u9879'}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 min-h-20 w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm text-text-primary outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}
