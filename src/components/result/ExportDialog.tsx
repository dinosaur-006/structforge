import { useState } from 'react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import type { FinalScript, RenderVersion } from '../../shared/types';

interface ExportDialogProps {
  open: boolean;
  isExporting: boolean;
  progress: number;
  renderStage?: string;
  outputUrl: string | null;
  script: FinalScript | null;
  defaultVersion: RenderVersion;
  renderDisabled?: boolean;
  renderDisabledReason?: string;
  onClose: () => void;
  onExport: (version: RenderVersion, resolution: string) => void;
  onDownloadJson: () => void;
  onDownloadSrt: () => void;
}

export function ExportDialog({ open, isExporting, progress, renderStage, outputUrl, script, defaultVersion, renderDisabled = false, renderDisabledReason, onClose, onExport, onDownloadJson, onDownloadSrt }: ExportDialogProps) {
  const [exportStarted, setExportStarted] = useState(false);

  const handleExport = () => {
    setExportStarted(true);
    onExport(defaultVersion, '1080p');
  };

  const handleClose = () => {
    if (!isExporting) {
      setExportStarted(false);
      onClose();
    }
  };

  return (
    <Modal
      open={open}
      title="导出视频"
      onClose={handleClose}
      footer={
        !exportStarted ? (
          <>
            <Button variant="ghost" onClick={handleClose}>取消</Button>
            <Button variant="primary" onClick={handleExport} disabled={renderDisabled}>
              导出 MP4 视频
            </Button>
          </>
        ) : outputUrl ? (
          <Button variant="ghost" onClick={handleClose}>关闭</Button>
        ) : null
      }
    >
      <div className="space-y-4">
        {!exportStarted ? (
          <>
            <p className="text-sm text-text-secondary">
              将生成 1080p 竖屏视频，自动包含字幕和背景音乐。
            </p>
            {renderDisabled && renderDisabledReason ? (
              <p className="rounded-xl border border-warning/40 bg-warning-muted p-3 text-sm text-text-secondary">{renderDisabledReason}</p>
            ) : null}
          </>
        ) : isExporting ? (
          <div className="space-y-3">
            <p className="text-sm font-medium text-text-primary">
              {renderStage
                ? renderStage
                : progress > 0 && progress < 100
                  ? `正在渲染分镜 ${Math.max(1, Math.round(progress / 20))}/5...`
                  : progress === 0
                    ? '正在启动渲染引擎...'
                    : '正在完成渲染...'}
            </p>
            <div className="flex justify-between text-xs text-text-secondary">
              <span>进度</span>
              <span>{progress > 0 ? `${Math.round(progress)}%` : '准备中'}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-border">
              <div
                className="progress-shimmer h-full rounded-full transition-all duration-700"
                style={{ width: `${Math.max(progress, 5)}%` }}
              />
            </div>
          </div>
        ) : outputUrl ? (
          <div className="space-y-4 text-center">
            <p className="text-sm font-medium text-success">视频渲染完成</p>
            <a
              href={outputUrl}
              download
              className="inline-flex min-h-11 items-center rounded-xl bg-primary px-6 text-sm font-semibold text-surface transition-colors hover:bg-primary-hover"
            >
              下载视频
            </a>
          </div>
        ) : null}

        {/* Script downloads — secondary */}
        {script ? (
          <div className="border-t border-border pt-4">
            <p className="mb-2 text-xs text-text-muted">同时下载脚本文件：</p>
            <div className="flex gap-2">
              <button onClick={onDownloadJson} className="text-xs text-text-secondary underline underline-offset-2 hover:text-primary">
                脚本 JSON
              </button>
              <button onClick={onDownloadSrt} className="text-xs text-text-secondary underline underline-offset-2 hover:text-primary">
                字幕 SRT
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
