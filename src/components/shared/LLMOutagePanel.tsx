import { AlertTriangle, Brain, RefreshCw, Wrench } from 'lucide-react';
import { Button } from '../ui/Button';

interface Props { operation: string; error: string; suggestion?: string; retryable?: boolean; onRetry: () => void; onWorkOffline: () => void; onDismiss?: () => void; }

export function LLMOutagePanel({ operation, error, suggestion, retryable = true, onRetry, onWorkOffline, onDismiss }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-md">
      <div className="mx-4 w-full max-w-lg rounded-2xl border border-[#EBEAE6] bg-white shadow-[0_0_40px_rgba(0,0,0,0.04)] overflow-hidden">
        <div className="px-6 pt-6 pb-4">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-[#FDF4F4]">
              <Brain className="h-5 w-5 text-[#D45A5A]" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#1C1C1E]">核心引擎暂时不可用</h2>
              <p className="text-sm text-[#8E8E93]">操作 <strong className="text-[#6E6E73]">{operation}</strong> 需要 AI 模型参与，但调用失败</p>
            </div>
          </div>
        </div>

        <div className="px-6 pb-3">
          <div className="rounded-xl bg-[#FDF4F4] px-4 py-3 flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-[#D45A5A]" />
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-[#D45A5A]">{error}</p>
              {suggestion && <p className="mt-1 text-[12px] text-[#D45A5A]/70">{suggestion}</p>}
            </div>
          </div>
        </div>

        <div className="px-6 pb-4">
          <div className="rounded-xl bg-[#FAFAF9] px-4 py-3 text-[12px] text-[#8E8E93]">
            <p className="font-medium text-[#6E6E73] mb-1">可能的原因：</p>
            <ul className="list-disc list-inside space-y-0.5">
              <li>API Key 无效、过期或未配置</li>
              <li>网络连接不稳定</li>
              <li>LLM 服务端暂时过载或维护中</li>
            </ul>
            <p className="mt-2">前往 <button type="button" className="underline text-[#C8843C] hover:text-[#B07530]" onClick={() => window.open('/settings', '_self')}>设置页面</button> 检查配置，或运行 <code className="rounded bg-white border border-[#EBEAE6] px-1.5 py-0.5 text-[11px] font-medium text-[#6E6E73]">GET /api/v1/diagnostics/llm</code></p>
          </div>
        </div>

        <div className="flex gap-2.5 px-6 pb-6">
          {retryable && <Button variant="primary" className="flex-1 text-[13px]" onClick={onRetry}><RefreshCw className="h-4 w-4 mr-1.5" />重试</Button>}
          <Button variant="secondary" className="flex-1 text-[13px]" onClick={onWorkOffline}><Wrench className="h-4 w-4 mr-1.5" />离线模式</Button>
        </div>

        <div className="border-t border-[#EBEAE6] bg-[#FAFAF9] px-6 py-3">
          <p className="text-[11px] text-[#AEAEB2] leading-relaxed">离线模式下，结构迁移和脚本生成将使用规则模板替代 AI 推理。生成的视频会带有「未经过 AI 优化」标记。建议优先解决连接问题后重试。</p>
        </div>
      </div>
    </div>
  );
}
