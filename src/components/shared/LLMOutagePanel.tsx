import { AlertTriangle, Brain, RefreshCw, Settings, Wrench } from 'lucide-react';
import { Button } from '../ui/Button';

interface LLMOutagePanelProps {
  /** The operation that failed, e.g. "结构分析", "脚本迁移" */
  operation: string;
  /** Human-readable error message from the backend */
  error: string;
  /** Suggested fix from the backend */
  suggestion?: string;
  /** Whether the error is retryable */
  retryable?: boolean;
  /** Called when user clicks "重试" */
  onRetry: () => void;
  /** Called when user chooses offline/rule-only mode */
  onWorkOffline: () => void;
  /** Called when user wants to dismiss the panel */
  onDismiss?: () => void;
}

/**
 * Full-screen interruption panel shown when the core LLM engine is unreachable.
 *
 * This is NOT a toast or a banner — it is a deliberate UX choice to halt the
 * product rather than silently degrade. LLM failure means StructForge's core
 * value (structure understanding + creative migration) is unavailable, and
 * the user deserves to know that clearly.
 */
export function LLMOutagePanel({
  operation,
  error,
  suggestion,
  retryable = true,
  onRetry,
  onWorkOffline,
  onDismiss,
}: LLMOutagePanelProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#050508]/90 backdrop-blur-md animate-in">
      <div className="mx-4 w-full max-w-lg rounded-2xl border border-red-500/20 bg-slate-900 shadow-[0_0_60px_rgba(239,68,68,0.08)] overflow-hidden">
        {/* Header — red pulse accent */}
        <div className="relative px-6 pt-6 pb-4">
          <div className="absolute top-0 left-1/4 w-1/2 h-px bg-gradient-to-r from-transparent via-red-500/60 to-transparent" />
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 flex-none place-items-center rounded-xl bg-red-500/10 ring-1 ring-red-500/20">
              <Brain className="h-6 w-6 text-red-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                核心引擎暂时不可用
              </h2>
              <p className="text-sm text-text-muted">
                操作 <strong className="text-text-secondary">"{operation}"</strong> 需要 AI 模型参与，但调用失败
              </p>
            </div>
          </div>
        </div>

        {/* Error detail */}
        <div className="px-6 pb-3">
          <div className="rounded-lg border border-red-500/10 bg-red-500/5 px-4 py-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-red-400" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-red-300">{error}</p>
                {suggestion && (
                  <p className="mt-1 text-xs text-red-400/70">{suggestion}</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Diagnostic info */}
        <div className="px-6 pb-4">
          <div className="rounded-lg border border-border bg-sidebar/50 px-4 py-3 text-xs text-text-muted">
            <p className="font-medium mb-1.5">可能的原因：</p>
            <ul className="list-disc list-inside space-y-0.5 text-text-muted/80">
              <li>API Key 无效、过期或未配置</li>
              <li>网络连接不稳定，无法访问火山引擎 ARK</li>
              <li>LLM 服务端暂时过载或维护中</li>
            </ul>
            <p className="mt-2">
              您可以前往{' '}
              <button
                type="button"
                className="underline text-primary hover:text-primary/80"
                onClick={() => window.open('/settings', '_self')}
              >
                设置页面
              </button>
              {' '}检查 API 配置，或使用{' '}
              <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-[10px]">
                GET /api/v1/diagnostics/llm
              </code>
              {' '}端点排查网络连通性。
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-6 pb-6">
          {retryable && (
            <Button variant="primary" className="flex-1" onClick={onRetry}>
              <RefreshCw className="h-4 w-4 mr-2" />
              重试
            </Button>
          )}
          <Button variant="secondary" className="flex-1" onClick={onWorkOffline}>
            <Wrench className="h-4 w-4 mr-2" />
            离线工作（仅使用规则引擎）
          </Button>
          {onDismiss && (
            <Button variant="ghost" size="icon" onClick={onDismiss}>
              <Settings className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Warning */}
        <div className="border-t border-red-500/10 bg-red-500/[0.02] px-6 py-3">
          <p className="text-[11px] text-red-400/60 leading-relaxed">
            ⚠️ 离线模式下，结构迁移和脚本生成将使用规则模板替代 AI 推理，质量显著降低。
            生成的视频会带有「未经过 AI 优化」标记。建议优先解决连接问题后重试。
          </p>
        </div>
      </div>
    </div>
  );
}
