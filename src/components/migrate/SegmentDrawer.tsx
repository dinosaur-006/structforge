import { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/Button';
import { Drawer } from '../ui/Drawer';
import type { Asset, ScriptSegment, SegmentType } from '../../shared/types';

interface SegmentDrawerProps {
  open: boolean;
  segment: ScriptSegment | null;
  assets: Asset[];
  onClose: () => void;
  onApply: (id: string, changes: Partial<ScriptSegment>) => void;
}

const segmentOptions: Array<{ value: SegmentType; label: string }> = [
  { value: 'hook', label: 'Hook' },
  { value: 'pain', label: '\u75db\u70b9' },
  { value: 'product', label: '\u4ea7\u54c1\u5f15\u5165' },
  { value: 'proof', label: '\u5356\u70b9\u8bc1\u660e' },
  { value: 'cta', label: 'CTA' },
];

export function SegmentDrawer({ open, segment, assets, onClose, onApply }: SegmentDrawerProps) {
  const [form, setForm] = useState<ScriptSegment | null>(segment);

  useEffect(() => {
    setForm(segment);
  }, [segment]);

  const title = useMemo(() => (segment ? `${'\u7f16\u8f91\u5206\u955c'}: ${segment.label}` : '\u7f16\u8f91\u5206\u955c'), [segment]);

  const activeForm = form ?? segment;
  if (!activeForm) return null;

  const update = <K extends keyof ScriptSegment>(key: K, value: ScriptSegment[K]) => setForm((current) => ({ ...(current ?? activeForm), [key]: value }));

  const apply = () => {
    const duration = Math.max(1, Number(activeForm.duration) || segment?.duration || 1);
    onApply(activeForm.id, {
      ...activeForm,
      duration,
      end: activeForm.start + duration,
      label: segmentOptions.find((option) => option.value === activeForm.type)?.label ?? activeForm.label,
    });
    onClose();
  };

  return (
    <Drawer
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{'\u53d6\u6d88'}</Button>
          <Button variant="primary" onClick={apply}>{'\u5e94\u7528\u66f4\u6539'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm font-semibold">
          {'\u7c7b\u578b'}
          <select value={activeForm.type} onChange={(event) => update('type', event.target.value as SegmentType)} className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            {segmentOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label className="block text-sm font-semibold">
          {'\u65f6\u957f'}
          <input
            type="number"
            min="1"
            value={activeForm.duration}
            onChange={(event) => update('duration', Number(event.target.value))}
            className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30"
          />
        </label>
        <label className="block text-sm font-semibold">
          {'\u811a\u672c'}
          <textarea value={activeForm.copy} onChange={(event) => update('copy', event.target.value)} className="mt-2 min-h-24 w-full rounded-xl border border-border bg-card px-3 py-2 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30" />
        </label>
        <label className="block text-sm font-semibold">
          {'\u753b\u9762\u63cf\u8ff0'}
          <textarea value={activeForm.visual} onChange={(event) => update('visual', event.target.value)} className="mt-2 min-h-24 w-full rounded-xl border border-border bg-card px-3 py-2 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30" />
        </label>
        <label className="block text-sm font-semibold">
          {'\u5339\u914d\u7d20\u6750'}
          <select value={activeForm.assetId ?? ''} onChange={(event) => update('assetId', event.target.value || undefined)} className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option value="">未绑定</option>
            {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.name}</option>)}
          </select>
        </label>
        <label className="block text-sm font-semibold">
          {'\u5b57\u5e55\u6a21\u677f'}
          <select value={activeForm.subtitlePreset ?? ''} onChange={(event) => update('subtitlePreset', event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option>{'\u9ec4\u5b57\u767d\u63cf\u8fb9'}</option>
            <option>{'\u767d\u5b57\u9ed1\u9634\u5f71'}</option>
            <option>{'\u6781\u7b80\u5c0f\u5b57\u5e55'}</option>
          </select>
        </label>
        <label className="block text-sm font-semibold">
          {'\u8f6c\u573a'}
          <select value={activeForm.transition ?? ''} onChange={(event) => update('transition', event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option>{'\u786c\u5207'}</option>
            <option>{'\u5de6\u6ed1'}</option>
            <option>{'\u7f29\u653e'}</option>
          </select>
        </label>
        <label className="flex items-center gap-3 text-sm font-semibold">
          <input type="checkbox" checked={Boolean(activeForm.locked)} onChange={(event) => update('locked', event.target.checked)} />
          {'\u9501\u5b9a\u6b64\u5206\u955c'}
        </label>
      </div>
    </Drawer>
  );
}
