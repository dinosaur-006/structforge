import { Camera, FilePenLine, Loader2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ProjectBrief } from '../../shared/types';
import { api } from '../../services/api';
import { Button } from '../ui/Button';

interface CreativeBriefPanelProps {
  brief?: ProjectBrief;
  suggested?: { productName: string; sellingPoints: string[] } | null;
  projectId: string;
  onSave: (brief: ProjectBrief) => Promise<void> | void;
}

export function CreativeBriefPanel({ brief, suggested, projectId, onSave }: CreativeBriefPanelProps) {
  const initialName = useMemo(() => {
    const fromBrief = brief?.productName?.trim();
    if (fromBrief) return fromBrief;
    return suggested?.productName ?? '';
  }, [brief?.productName, suggested?.productName]);

  const initialPoints = useMemo(() => {
    const fromBrief = brief?.sellingPoints;
    if (fromBrief && fromBrief.length > 0) return fromBrief.join('\n');
    return (suggested?.sellingPoints ?? []).join('\n');
  }, [brief?.sellingPoints, suggested?.sellingPoints]);

  const [productName, setProductName] = useState(initialName);
  const [sellingPoints, setSellingPoints] = useState(initialPoints);
  const [uploading, setUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [visionResult, setVisionResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setProductName(initialName);
    setSellingPoints(initialPoints);
  }, [initialName, initialPoints]);

  const save = () => {
    void onSave({
      productName: productName.trim(),
      sellingPoints: sellingPoints.split(/\r?\n/).map((s) => s.trim()).filter(Boolean),
      targetAudience: '',
      offer: '',
      tone: '',
      mandatoryClaims: [],
    });
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setUploading(true);
    setVisionResult(null);
    // Show local preview immediately
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    try {
      const result = await api.analyzeProductImage(projectId, file);
      if (result.status === 'ok' && result.tags.length > 0) {
        setVisionResult(`AI 识别: ${result.tags.slice(0, 5).join('、')}${result.colors?.length ? ` · 主色: ${result.colors.slice(0, 2).join(', ')}` : ''}`);
      } else {
        setVisionResult('AI 视觉分析未返回结果，将使用文本描述生成图片');
      }
    } catch {
      setVisionResult('上传失败，将使用文本描述生成图片');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/60 bg-card px-5 py-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FilePenLine className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-sm">你要推广什么产品？</h2>
        </div>
        <Button size="sm" variant="secondary" onClick={save}>保存</Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <input
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="输入你的产品名称，例如：元气森林气泡水"
            className="h-10 w-full rounded-xl border border-border/60 bg-white px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            onBlur={save}
          />
          <textarea
            value={sellingPoints}
            onChange={(e) => setSellingPoints(e.target.value)}
            placeholder={"输入核心卖点（每行一个）\n例如：\n0糖0脂0卡\n真实果汁添加\n气泡口感清爽"}
            className="mt-3 min-h-[60px] w-full resize-none rounded-xl border border-border/60 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            onBlur={save}
          />
        </div>
        <div>
          {/* Product image upload */}
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-sidebar/30 p-4">
            {previewUrl ? (
              <div className="relative">
                <img src={previewUrl} alt="产品图预览" className="h-32 w-32 rounded-xl object-cover" />
                <button
                  type="button"
                  className="absolute -right-1 -top-1 rounded-full bg-white border border-border p-0.5 text-text-muted hover:text-error"
                  onClick={() => { setPreviewUrl(null); setVisionResult(null); if (fileRef.current) fileRef.current.value = ''; }}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ) : (
              <Camera className="h-8 w-8 text-text-muted" />
            )}
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => void handleUpload(e)}
            />
            <button
              type="button"
              disabled={uploading}
              className="flex items-center gap-1.5 rounded-xl border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Camera className="h-3 w-3" />}
              {previewUrl ? '更换产品图' : '上传产品图（可选）'}
            </button>
            {visionResult && (
              <p className="text-[10px] text-accent text-center leading-relaxed">{visionResult}</p>
            )}
            {!visionResult && !uploading && (
              <p className="text-[10px] text-text-muted text-center">上传后 AI 分析产品外观，生成更精准的图片</p>
            )}
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs text-text-muted">请输入你<span className="text-text-secondary font-medium">自己产品</span>的名称和卖点。AI 会基于样例视频的结构为你生成新脚本。</p>
    </div>
  );
}
