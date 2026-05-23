import { useState } from 'react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import type { RenderResolution, RenderVersion } from '../../shared/types';

interface ExportDialogProps {
  open: boolean;
  isExporting: boolean;
  progress: number;
  outputUrl: string | null;
  defaultVersion: RenderVersion;
  onClose: () => void;
  onExport: (version: RenderVersion, resolution: RenderResolution) => void;
}

export function ExportDialog({ open, isExporting, progress, outputUrl, defaultVersion, onClose, onExport }: ExportDialogProps) {
  const [resolution, setResolution] = useState<RenderResolution>('1080p');
  const [version, setVersion] = useState<RenderVersion>(defaultVersion);
  return (
    <Modal
      open={open}
      title={'\u5bfc\u51fa\u7ed3\u679c'}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{'\u53d6\u6d88'}</Button>
          <Button variant="primary" onClick={() => onExport(version, resolution)} disabled={isExporting}>{isExporting ? '\u6b63\u5728\u751f\u6210...' : '\u5f00\u59cb\u5bfc\u51fa'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm font-semibold">
          {'\u7248\u672c'}
          <select value={version} onChange={(event) => setVersion(event.target.value as RenderVersion)} className="mt-2 h-11 w-full rounded-lg border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option value="original">{'\u539f\u7248'}</option>
            <option value="safe_fix">{'\u4fdd\u5b88\u4fee\u590d'}</option>
            <option value="strong_hook">{'Strong Hook'}</option>
            <option value="strong_conversion">{'\u5f3a\u8f6c\u5316'}</option>
          </select>
        </label>
        <label className="block text-sm font-semibold">
          MP4
          <select value={resolution} onChange={(event) => setResolution(event.target.value as RenderResolution)} className="mt-2 h-11 w-full rounded-lg border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
          </select>
        </label>
        {['SRT \u5b57\u5e55', 'PDF \u5206\u955c\u62a5\u544a', 'JSON \u7ed3\u6784\u6a21\u677f'].map((item) => (
          <label key={item} className="flex items-center gap-3 text-sm font-semibold">
            <input type="checkbox" defaultChecked />
            {item}
          </label>
        ))}
        {isExporting ? (
          <div className="rounded-lg border border-border bg-sidebar p-3">
            <div className="flex justify-between text-sm font-semibold">
              <span>{'\u6e32\u67d3\u8fdb\u5ea6'}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-border">
              <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
            </div>
          </div>
        ) : null}
        {outputUrl ? (
          <a href={outputUrl} className="inline-flex min-h-11 items-center rounded-lg border border-primary px-4 text-sm font-semibold text-primary hover:bg-sidebar">
            {'\u4e0b\u8f7d\u89c6\u9891'}
          </a>
        ) : null}
      </div>
    </Modal>
  );
}
