import { CheckCircle2, RefreshCcw, Rocket, Upload, Video } from 'lucide-react';
import { useRef, useState } from 'react';
import { ErrorAlert } from '../ui/ErrorAlert';
import { Button } from '../ui/Button';
import { cn } from '../../shared/cn';

interface VideoUploaderProps {
  file: File | null;
  onFile: (file: File | null) => void;
  onFiles?: (files: File[]) => void;
  onStart: () => void;
  disabled?: boolean;
  fileCount?: number;
}

export function VideoUploader({ file, onFile, onFiles, onStart, disabled, fileCount = file ? 1 : 0 }: VideoUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');

  const acceptFiles = (selected: File[]) => {
    const nextFiles = selected.slice(0, 3);
    if (!nextFiles.length) return;
    if (nextFiles.some((nextFile) => !nextFile.type.startsWith('video/'))) {
      setError('\u4ec5\u652f\u6301 MP4 / MOV \u7b49\u89c6\u9891\u6587\u4ef6');
      onFile(null);
      onFiles?.([]);
      return;
    }
    setError('');
    onFile(nextFiles[0]);
    onFiles?.(nextFiles);
  };

  return (
    <div className="space-y-4">
      {error ? <ErrorAlert title={'\u4e0a\u4f20\u5931\u8d25'} description={error} /> : null}
      <div
        className={cn(
          'rounded-lg border border-dashed bg-card p-6 shadow-sm transition-colors duration-200 md:p-8',
          dragging ? 'border-primary bg-sidebar' : 'border-border hover:border-primary/50',
        )}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          acceptFiles(Array.from(event.dataTransfer.files));
        }}
      >
        <input
          ref={inputRef}
          aria-label={'\u9009\u62e9\u89c6\u9891'}
          className="sr-only"
          type="file"
          multiple
          onChange={(event) => acceptFiles(Array.from(event.target.files ?? []))}
        />
        {!file ? (
          <div className="flex flex-col items-center justify-center text-center">
            <div className="mb-5 grid h-20 w-20 place-items-center rounded-lg border border-border bg-sidebar text-primary">
              <Upload className="h-9 w-9" />
            </div>
            <h2 className="text-xl font-semibold">{'\u62d6\u62fd\u89c6\u9891\u5230\u6b64\u5904\uff0c\u6216\u70b9\u51fb\u4e0a\u4f20'}</h2>
            <p className="mt-2 text-sm text-text-secondary">{'\u652f\u6301 MP4 / MOV\uff0c\u53ef\u9009 1-3 \u6761\u6837\u4f8b\uff0c\u5355\u6587\u4ef6\u6700\u5927 500MB'}</p>
            <Button className="mt-6" variant="primary" onClick={() => inputRef.current?.click()}>
              <Video className="h-4 w-4" />
              {'\u9009\u62e9\u6587\u4ef6'}
            </Button>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-[180px,1fr]">
            <div className="grid aspect-[9/16] max-h-64 place-items-center rounded-lg border border-border bg-sidebar">
              <Video className="h-12 w-12 text-primary" />
            </div>
            <div className="flex flex-col justify-center">
              <div className="flex items-center gap-2 text-success">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-semibold">
                  {fileCount > 1 ? `\u5df2\u9009\u62e9\uff1a${fileCount} \u6761\u6837\u4f8b\u89c6\u9891` : `\u5df2\u4e0a\u4f20\uff1a${file.name}`}
                </span>
              </div>
              <p className="mt-3 text-sm text-text-secondary">35s {'\u00b7'} 1080x1920 {'\u00b7'} 42MB</p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={disabled}>
                  <RefreshCcw className="h-4 w-4" />
                  {'\u6dfb\u52a0\u6216\u66ff\u6362\u6837\u4f8b'}
                </Button>
                <Button variant="primary" onClick={onStart} disabled={disabled}>
                  <Rocket className="h-4 w-4" />
                  {fileCount > 1 ? `\u5206\u6790 ${fileCount} \u6761\u6837\u4f8b` : '\u5f00\u59cb\u5206\u6790'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
