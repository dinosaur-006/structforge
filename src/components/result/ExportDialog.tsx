import { useState } from 'react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import type { FinalScript, RenderResolution, RenderVersion } from '../../shared/types';

interface ExportDialogProps {
  open: boolean;
  isExporting: boolean;
  progress: number;
  outputUrl: string | null;
  script: FinalScript | null;
  defaultVersion: RenderVersion;
  onClose: () => void;
  onExport: (version: RenderVersion, resolution: RenderResolution) => void;
  onDownloadJson: () => void;
  onDownloadSrt: () => void;
}

export function ExportDialog({ open, isExporting, progress, outputUrl, script, defaultVersion, onClose, onExport, onDownloadJson, onDownloadSrt }: ExportDialogProps) {
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
        <div className="rounded-lg border border-border bg-sidebar/40 p-3">
          <p className="text-sm font-semibold">{'\u811a\u672c\u8d44\u4ea7'}</p>
          <p className="mt-1 text-xs text-text-secondary">{'\u4e0b\u8f7d\u5f53\u524d\u5df2\u751f\u6210\u811a\u672c\u7684\u7ed3\u6784\u6570\u636e\u4e0e\u5b57\u5e55\u3002'}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={onDownloadJson} disabled={!script}>{'\u4e0b\u8f7d\u811a\u672c JSON'}</Button>
            <Button variant="secondary" size="sm" onClick={onDownloadSrt} disabled={!script}>{'\u4e0b\u8f7d\u5b57\u5e55 SRT'}</Button>
          </div>
        </div>
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
