import { FilePenLine } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { ProjectBrief } from '../../shared/types';
import { Button } from '../ui/Button';

interface CreativeBriefPanelProps {
  brief?: ProjectBrief;
  suggested?: { productName: string; sellingPoints: string[] } | null;
  onSave: (brief: ProjectBrief) => Promise<void> | void;
}

export function CreativeBriefPanel({ brief, suggested, onSave }: CreativeBriefPanelProps) {
  // ── Use suggested values immediately when brief is empty ──
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

  // Sync when brief or suggested changes externally
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

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FilePenLine className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-sm">你要推广什么产品？</h2>
        </div>
        <Button size="sm" variant="secondary" onClick={save}>保存</Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <input
          value={productName}
          onChange={(e) => setProductName(e.target.value)}
          placeholder="输入你的产品名称，例如：元气森林气泡水"
          className="h-10 rounded-lg border border-border bg-card px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          onBlur={save}
        />
        <textarea
          value={sellingPoints}
          onChange={(e) => setSellingPoints(e.target.value)}
          placeholder="输入核心卖点（每行一个）&#10;例如：&#10;0糖0脂0卡&#10;真实果汁添加&#10;气泡口感清爽"
          className="min-h-[60px] resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          onBlur={save}
        />
      </div>
      <p className="mt-2 text-xs text-text-muted">请输入你<span className="text-text-secondary font-medium">自己产品</span>的名称和卖点。AI 会基于样例视频的结构为你生成新脚本。不要填样例视频里的产品。</p>
    </div>
  );
}
