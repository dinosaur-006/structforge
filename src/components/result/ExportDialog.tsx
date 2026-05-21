import { useState } from 'react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';

interface ExportDialogProps {
  open: boolean;
  isExporting: boolean;
  onClose: () => void;
  onExport: () => void;
}

export function ExportDialog({ open, isExporting, onClose, onExport }: ExportDialogProps) {
  const [resolution, setResolution] = useState('1080p');
  return (
    <Modal
      open={open}
      title={'\u5bfc\u51fa\u7ed3\u679c'}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{'\u53d6\u6d88'}</Button>
          <Button variant="primary" onClick={onExport} disabled={isExporting}>{isExporting ? '\u6b63\u5728\u751f\u6210...' : '\u5f00\u59cb\u5bfc\u51fa'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm font-semibold">
          MP4
          <select value={resolution} onChange={(event) => setResolution(event.target.value)} className="mt-2 h-11 w-full rounded-lg border border-border bg-card px-3 outline-none focus:border-primary focus:ring-2 focus:ring-primary/30">
            <option>720p</option>
            <option>1080p</option>
          </select>
        </label>
        {['SRT \u5b57\u5e55', 'PDF \u5206\u955c\u62a5\u544a', 'JSON \u7ed3\u6784\u6a21\u677f'].map((item) => (
          <label key={item} className="flex items-center gap-3 text-sm font-semibold">
            <input type="checkbox" defaultChecked />
            {item}
          </label>
        ))}
      </div>
    </Modal>
  );
}
