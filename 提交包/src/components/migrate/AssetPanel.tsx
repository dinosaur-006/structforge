import { Film, Image, Loader2, Upload, CheckCircle2, AlertCircle } from 'lucide-react';
import type { Asset } from '../../shared/types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

function AssetCard({ asset, projectId }: { asset: Asset; projectId: string }) {
  const Icon = asset.type === 'video' ? Film : Image;
  const isMatched = asset.matchStatus === 'matched';
  const isPartial = asset.matchStatus === 'partial';
  const thumbnailUrl = asset.type !== 'text'
    ? `${API_BASE_URL}/api/v1/assets/${projectId}/${asset.id}/thumbnail`
    : null;
  const isReference = asset.origin === 'reference' || (asset.analysis && (asset.analysis as any).reference_source);

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-[#EBEAE6] bg-white hover:border-[#D1CFC8] transition-colors">
      <div className="w-14 h-14 rounded-xl bg-[#FAFAF9] border border-[#EBEAE6] flex items-center justify-center overflow-hidden flex-shrink-0">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={asset.name} className="w-full h-full object-cover" loading="lazy"
            onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
        ) : (
          <Icon className="w-5 h-5 text-[#AEAEB2]" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-[13px] font-medium text-[#1C1C1E] truncate">{asset.name}</p>
          {isReference && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F5F2EC] text-[#C8843C] font-medium flex-shrink-0">参考</span>
          )}
        </div>
        <p className="text-[11px] text-[#AEAEB2] mt-0.5">{asset.tag || (isReference ? '参考视频原片' : '用户上传')}</p>
      </div>
      {isMatched && (
        <div className="flex items-center gap-1 text-[11px] font-medium text-[#4A9E7C] flex-shrink-0">
          <CheckCircle2 className="w-3.5 h-3.5" />
          {asset.matchScore}%
        </div>
      )}
      {isPartial && (
        <div className="flex items-center gap-1 text-[11px] font-medium text-[#C8843C] flex-shrink-0">
          <AlertCircle className="w-3.5 h-3.5" />
          {asset.matchScore}%
        </div>
      )}
    </div>
  );
}

interface AssetPanelProps {
  assets: Asset[];
  assetLoading?: boolean;
  onUploadAsset?: (file: File) => Promise<void> | void;
  projectId?: string;
}

export function AssetPanel({ assets, assetLoading = false, onUploadAsset, projectId = '' }: AssetPanelProps) {
  const handleUpload = (file: File | undefined) => {
    if (!file || !onUploadAsset) return;
    void onUploadAsset(file);
  };

  const userAssets = assets.filter(a => !(a.analysis && (a.analysis as any).reference_source));
  const refAssets = assets.filter(a => a.analysis && (a.analysis as any).reference_source);

  return (
    <div className="space-y-4">
      {/* Upload area */}
      <label className="block cursor-pointer rounded-xl border border-dashed border-[#D1CFC8] bg-[#FAFAF9] p-6 text-center transition-colors hover:border-[#C8843C]/40 hover:bg-[#F5F2EC]/50">
        {assetLoading ? (
          <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-[#C8843C]/60" />
        ) : (
          <Upload className="mx-auto mb-2 h-5 w-5 text-[#C8843C]/60" />
        )}
        <p className="text-[13px] font-medium text-[#6E6E73]">
          {assetLoading ? '正在上传分析…' : '拖拽或点击上传素材'}
        </p>
        <p className="text-[11px] text-[#AEAEB2] mt-1">图片 / 视频，上传后自动匹配分镜槽位</p>
        <input
          aria-label="上传素材"
          className="sr-only"
          type="file"
          accept="image/*,video/*"
          disabled={assetLoading || !onUploadAsset}
          onChange={e => {
            handleUpload(e.currentTarget.files?.[0]);
            e.currentTarget.value = '';
          }}
        />
      </label>

      {/* Asset list */}
      {assets.length > 0 && (
        <div className="space-y-2">
          {userAssets.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-[#AEAEB2]">用户素材 · {userAssets.length} 个</p>
              {userAssets.map(a => <AssetCard key={a.id} asset={a} projectId={projectId} />)}
            </div>
          )}
          {refAssets.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-[#AEAEB2]">参考视频 · {refAssets.length} 个</p>
              {refAssets.map(a => <AssetCard key={a.id} asset={a} projectId={projectId} />)}
            </div>
          )}
        </div>
      )}

      {assets.length === 0 && !assetLoading && (
        <div className="text-center py-4">
          <p className="text-[12px] text-[#AEAEB2]">暂无素材</p>
          <p className="text-[11px] text-[#D1CFC8] mt-0.5">上传产品图片或视频片段，AI 会自动匹配到对应分镜</p>
        </div>
      )}
    </div>
  );
}
