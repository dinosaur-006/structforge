import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { FileText, Film, Image, Loader2, Upload } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import type { Asset } from '../../shared/types';

function AssetCard({ asset }: { asset: Asset }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: asset.id });
  const Icon = asset.type === 'video' ? Film : asset.type === 'text' ? FileText : Image;
  const tone = asset.matchStatus === 'matched' ? 'success' : asset.matchStatus === 'partial' ? 'warning' : 'neutral';

  return (
    <div
      ref={setNodeRef}
      className="rounded-lg border border-border bg-card p-3 shadow-sm transition-colors hover:border-primary/40"
      style={{ transform: CSS.Translate.toString(transform) }}
      {...listeners}
      {...attributes}
    >
      <div className="grid aspect-video place-items-center rounded-lg border border-border bg-sidebar" style={{ color: asset.color }}>
        <Icon className="h-7 w-7" />
      </div>
      <div className="mt-3">
        <p className="truncate text-sm font-semibold">{asset.name}</p>
        <p className="mt-1 text-xs text-text-secondary">{asset.tag}</p>
        <Badge className="mt-2" tone={tone}>{asset.matchScore}%</Badge>
        <p className="mt-2 line-clamp-2 text-xs leading-5 text-text-secondary">{asset.reason}</p>
      </div>
    </div>
  );
}

interface AssetPanelProps {
  assets: Asset[];
  assetLoading?: boolean;
  onUploadAsset?: (file: File) => Promise<void> | void;
}

export function AssetPanel({ assets, assetLoading = false, onUploadAsset }: AssetPanelProps) {
  const handleUpload = (file: File | undefined) => {
    if (!file || !onUploadAsset) return;
    void onUploadAsset(file);
  };

  return (
    <aside className="space-y-4 rounded-lg border border-border bg-card p-4 shadow-sm lg:w-64 lg:flex-none">
      <label className="block cursor-pointer rounded-lg border border-dashed border-border bg-sidebar/50 p-4 text-center text-sm text-text-secondary transition-colors hover:border-primary/50">
        {assetLoading ? (
          <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
        ) : (
          <Upload className="mx-auto mb-2 h-6 w-6 text-primary" />
        )}
        <span>{assetLoading ? '\u6b63\u5728\u4e0a\u4f20' : '\u62d6\u62fd\u6216\u70b9\u51fb\u4e0a\u4f20'}</span>
        <input
          aria-label="上传素材"
          className="sr-only"
          type="file"
          accept="image/*,video/*,text/plain"
          disabled={assetLoading || !onUploadAsset}
          onChange={(event) => {
            handleUpload(event.currentTarget.files?.[0]);
            event.currentTarget.value = '';
          }}
        />
      </label>
      <h2 className="font-semibold">{'\u7d20\u6750\u5217\u8868'}</h2>
      {assets.length === 0 ? (
        <EmptyState icon={<Upload className="h-7 w-7" />} title={'\u6682\u65e0\u7d20\u6750'} description={'\u8bf7\u4e0a\u4f20\u4ea7\u54c1\u56fe\u6216\u89c6\u9891\u7247\u6bb5'} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          {assets.map((asset) => <AssetCard key={asset.id} asset={asset} />)}
        </div>
      )}
    </aside>
  );
}
