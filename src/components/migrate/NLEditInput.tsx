import { Sparkles, Wand2 } from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';

interface NLEditInputProps {
  onCommand: (command: string) => Promise<void>;
  loading: boolean;
}

const suggestions = [
  '让开头更抓人一些',
  '缩短证明部分到8秒',
  '把产品介绍提前',
  '减少字幕，增强节奏感',
  '让CTA更有紧迫感',
  '增加视觉描述的细节',
  '把卖点顺序调整为先讲续航再讲降噪',
];

export function NLEditInput({ onCommand, loading }: NLEditInputProps) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Ctrl+K to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape') {
        setOpen(false);
        setFeedback(null);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const submit = useCallback(async () => {
    const cmd = value.trim();
    if (!cmd || loading) return;
    setValue('');
    setFeedback(null);
    try {
      await onCommand(cmd);
      setFeedback(`已应用: ${cmd}`);
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback('编辑失败，请重试');
    }
  }, [value, loading, onCommand]);

  return (
    <div className="relative">
      {!open ? (
        <button
          type="button"
          className="flex items-center gap-2 rounded-lg border border-dashed border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-primary/50 hover:text-primary"
          onClick={() => setOpen(true)}
        >
          <Wand2 className="h-4 w-4" />
          自然语言编辑
          <kbd className="ml-2 hidden rounded border border-border bg-sidebar px-1.5 py-0.5 font-mono text-xs sm:inline">
            Ctrl+K
          </kbd>
        </button>
      ) : (
        <div className="flex w-full items-center gap-2 rounded-lg border-2 border-primary bg-card px-4 py-2 shadow-lg">
          <Sparkles className="h-4 w-4 flex-none text-primary" />
          <input
            ref={inputRef}
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-secondary"
            placeholder="描述你想怎么改，例如：让开头更抓人..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void submit();
              if (e.key === 'Escape') setOpen(false);
            }}
            disabled={loading}
          />
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-1 text-xs font-semibold text-white transition-opacity hover:opacity-85 disabled:opacity-50"
            disabled={!value.trim() || loading}
            onClick={() => void submit()}
          >
            {loading ? '执行中...' : '执行'}
          </button>
          <button
            type="button"
            className="text-xs text-text-secondary hover:text-text-primary"
            onClick={() => setOpen(false)}
          >
            Esc
          </button>
        </div>
      )}

      {/* Suggestions */}
      {open ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-text-secondary transition-colors hover:border-primary/40 hover:text-text-primary"
              onClick={() => { setValue(s); inputRef.current?.focus(); }}
            >
              {s}
            </button>
          ))}
        </div>
      ) : null}

      {/* Feedback */}
      {feedback ? (
        <p className="mt-2 text-xs text-primary animate-in fade-in">{feedback}</p>
      ) : null}
    </div>
  );
}
