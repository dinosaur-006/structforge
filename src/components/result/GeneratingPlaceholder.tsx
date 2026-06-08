import { Loader2, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';

interface GeneratingPlaceholderProps {
  slotId: string;
  label: string;
  description: string;   // e.g. "AI 正在生成结尾 CTA 画面..."
  estimatedSeconds?: number;
  onComplete?: (slotId: string, assetUrl: string) => void;
}

const WS_BASE = (import.meta.env.VITE_WS_URL as string | undefined) ??
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/^http/, 'ws') ??
  'ws://127.0.0.1:8000';

export function GeneratingPlaceholder({
  slotId,
  label,
  description,
  estimatedSeconds = 45,
  onComplete,
}: GeneratingPlaceholderProps) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'connecting' | 'generating' | 'completed' | 'failed'>('connecting');
  const [statusMessage, setStatusMessage] = useState('正在连接...');

  // Simulated progress animation (0 → 95%, then waits for real completion)
  useEffect(() => {
    if (status !== 'generating') return;
    const interval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 1, 92));
    }, (estimatedSeconds * 1000) / 92);
    return () => clearInterval(interval);
  }, [status, estimatedSeconds]);

  // WebSocket connection for real generation status
  useEffect(() => {
    const wsUrl = `${WS_BASE}/ws/generation/${slotId}`;
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => {
        setStatus('generating');
        setStatusMessage('AI 生成中...');
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.status === 'generating') {
            if (data.progress) setProgress(Math.round(data.progress * 100));
            if (data.message) setStatusMessage(data.message);
          } else if (data.status === 'completed') {
            setProgress(100);
            setStatus('completed');
            setStatusMessage('生成完成！');
            if (data.asset_url && onComplete) {
              setTimeout(() => onComplete(slotId, data.asset_url), 600);
            }
          } else if (data.status === 'failed') {
            setStatus('failed');
            setStatusMessage(data.error || '生成失败');
          }
        } catch {
          // Ignore parse errors
        }
      };
      ws.onerror = () => setStatusMessage('连接中断，正在重连...');
      ws.onclose = () => {
        if (status !== 'completed' && status !== 'failed') {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };
    }

    connect();
    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimer);
    };
  }, [slotId, onComplete]);

  return (
    <div className="relative rounded-lg border border-border bg-card overflow-hidden">
      {/* Animated background pulse */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          background: status === 'completed'
            ? 'radial-gradient(circle at 50% 50%, rgba(16,185,129,0.3), transparent 70%)'
            : status === 'failed'
              ? 'radial-gradient(circle at 50% 50%, rgba(239,68,68,0.3), transparent 70%)'
              : 'radial-gradient(circle at 50% 50%, rgba(99,102,241,0.3), transparent 70%)',
        }}
      />

      <div className="relative flex flex-col items-center justify-center p-8 min-h-[180px]">
        {/* Icon */}
        <div className="mb-4">
          {status === 'completed' ? (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/20">
              <Sparkles className="h-6 w-6 text-success" />
            </div>
          ) : status === 'failed' ? (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-error/20">
              <span className="text-xl">⚠</span>
            </div>
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/20">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          )}
        </div>

        {/* Label */}
        <p className="text-sm font-semibold text-text-primary">{label}</p>

        {/* Status text */}
        <p className="mt-1 text-xs text-text-secondary">{description}</p>
        <p className="mt-0.5 text-xs text-text-muted">{statusMessage}</p>

        {/* Progress bar */}
        <div className="mt-4 h-1.5 w-full max-w-[240px] rounded-full bg-sidebar overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              status === 'completed' ? 'bg-success' :
              status === 'failed' ? 'bg-error' :
              'bg-primary'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Estimated time */}
        {status === 'generating' && progress < 90 && (
          <p className="mt-2 text-[10px] text-text-muted">
            预计还需 {Math.ceil(estimatedSeconds * (1 - progress / 100))} 秒
          </p>
        )}
      </div>
    </div>
  );
}
