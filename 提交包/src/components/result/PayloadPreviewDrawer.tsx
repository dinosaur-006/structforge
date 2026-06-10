import { Code2, Copy, Cpu, DollarSign, Download, Key, Layers, PlayCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '../ui/Button';
import { Drawer } from '../ui/Drawer';
import type { BlueprintSegmentPayload, BlueprintPayloadsResponse } from '../../shared/types';

interface PayloadPreviewDrawerProps {
  open: boolean;
  onClose: () => void;
  payloads: BlueprintPayloadsResponse | null;
  loading: boolean;
  selectedSegmentId: string | null;
  videoGenAvailable: boolean;
  onRenderRequest?: () => void;
  isRendering?: boolean;
}

const CAMERA_LABELS: Record<string, string> = {
  '静态': 'Locked-off Tripod',
  '缓推': 'Cinematic Slow Push-in',
  '快推': 'Dynamic Fast Zoom-in',
  '拉远': 'Dramatic Pull-back',
  '横移': 'Elegant Dolly Track',
  '跟随': 'Smooth Follow-cam',
  '手持微晃': 'Handheld Shake',
};

const FX_LABELS: Record<string, string> = {
  '无': 'No FX · Pure Render',
  '震屏': 'Screen Shake',
  '闪白': 'Flash Exposure',
  '慢动作': '120fps Slow-mo',
  '放大': 'Crash Zoom',
  '模糊过渡': 'Lens Blur Transition',
};

const TYPE_LABELS: Record<string, string> = {
  hook: '开场吸引',
  pain: '用户痛点',
  product: '产品展示',
  proof: '信任背书',
  cta: '立即行动',
  demo: '效果演示',
  offer: '限时优惠',
  compare: '对比优势',
};

export function PayloadPreviewDrawer({
  open,
  onClose,
  payloads,
  loading,
  selectedSegmentId,
  videoGenAvailable,
  onRenderRequest,
  isRendering = false,
}: PayloadPreviewDrawerProps) {
  const selectedPayload = useMemo(() => {
    if (!payloads?.payloads || !selectedSegmentId) return null;
    return payloads.payloads.find((p) => p.segment_id === selectedSegmentId) ?? null;
  }, [payloads, selectedSegmentId]);

  const allPayloads = payloads?.payloads ?? [];
  const [renderClicked, setRenderClicked] = useState(false);

  const handleRenderClick = () => {
    setRenderClicked(true);
    onRenderRequest?.();
  };

  return (
    <Drawer
      open={open}
      title="AI 渲染调度参数 · Pre-viz 蓝图"
      onClose={onClose}
      footer={
        videoGenAvailable ? (
          // ── API Available: One-click render button ──
          <div className="space-y-2">
            {!renderClicked ? (
              <Button
                variant="primary"
                className="w-full bg-green-600 hover:bg-green-500 border-green-400/30"
                onClick={handleRenderClick}
              >
                <PlayCircle className="h-4 w-4 mr-2" />
                一键渲染 · 提交至 RunningHub Flux
              </Button>
            ) : (
              <Button variant="primary" className="w-full" disabled>
                <span className="inline-block h-3.5 w-3.5 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {isRendering ? '渲染中...' : '已提交渲染任务'}
              </Button>
            )}
            <p className="text-[10px] text-text-muted text-center">
              提交后将调用 RunningHub Flux 替换所有 AI 蓝图卡为真实视频画面
            </p>
          </div>
        ) : (
          // ── API Unavailable: Guide to configure ──
          <Button
            variant="primary"
            className="w-full"
            onClick={() => {
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          >
            <Key className="h-4 w-4 mr-2" />
            配置 Flux API 密钥以解锁真实画面
          </Button>
        )
      }
    >
      <div className="flex flex-col h-full space-y-4 text-[#6E6E73]">
        {/* ── Amber warning banner (API unavailable) or green ready banner ── */}
        {!videoGenAvailable ? (
          <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
            <p className="text-sm text-[#C8843C]/90 leading-relaxed">
              <span className="font-bold">引擎就绪：</span>
              系统已完成物理引擎层面的分镜排期与提示词规划。检测到大模型 API 未配置，
              目前已为您渲染时间线骨架。画面为静态蓝图卡，音频（TTS · BGM）完整播放。
            </p>
          </div>
        ) : (
          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
            <p className="text-sm text-emerald-400/90 leading-relaxed">
              <span className="font-bold">API 已连接：</span>
              RunningHub Flux 就绪，可随时下发真实 AI 渲染任务。
              点击底部「一键渲染」按钮提交 Payload，替换蓝图卡为真实视频画面。
            </p>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin h-6 w-6 border-2 border-primary/30 border-t-primary rounded-full" />
            <span className="ml-3 text-sm text-text-muted">加载蓝图数据...</span>
          </div>
        )}

        {/* No payloads */}
        {!loading && allPayloads.length === 0 && (
          <div className="text-center py-8">
            <Layers className="mx-auto h-10 w-10 text-text-muted mb-3" />
            <p className="text-sm text-text-muted">当前脚本无 AI 生成预留位</p>
            <p className="text-xs text-text-muted mt-1">
              所有分镜均已使用上传素材或包装补全，无需 AI 生成。
            </p>
          </div>
        )}

        {/* Segment selector */}
        {!loading && allPayloads.length > 0 && (
          <div>
            <p className="text-xs font-medium text-text-muted mb-2 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" />
              选择分镜查看渲染参数 ({allPayloads.length} 个预留位)
            </p>
            <div className="flex flex-wrap gap-2">
              {allPayloads.map((p) => (
                <button
                  key={p.segment_id}
                  type="button"
                  className={`rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
                    selectedSegmentId === p.segment_id
                      ? 'border-primary/40 bg-primary-muted text-primary'
                      : 'border-border-visible text-text-secondary hover:border-primary/30'
                  }`}
                  onClick={() => {
                    // The selection happens in the parent via the store
                  }}
                >
                  {TYPE_LABELS[p.segment_type] ?? p.segment_type}
                  <span className="ml-1 text-text-muted">· {p.duration.toFixed(1)}s</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Selected segment detail */}
        {selectedPayload && (
          <PayloadDetail payload={selectedPayload} />
        )}

        {/* ── Billing & cost summary ── */}
        {!loading && payloads && allPayloads.length > 0 && (
          <div className="pt-4 border-t border-[#EBEAE6]00 space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span className="text-slate-400">预估算力消耗：</span>
              <div className="text-right">
                <div className="font-mono text-slate-200">
                  {payloads.total_estimated_tokens.toLocaleString()} Tokens
                </div>
                <div className="font-mono text-emerald-500 text-xs">
                  ≈ ${payloads.total_estimated_cost_usd.toFixed(3)} USD
                </div>
              </div>
            </div>

            {/* ── Export buttons ── */}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className="flex items-center justify-center gap-1.5 rounded-xl border border-[#EBEAE6] bg-[#FAFAF9]/50 px-3 py-2 text-[11px] text-[#6E6E73] hover:border-[#D1CFC8] hover:text-[#1C1C1E] transition-colors"
                onClick={() => {
                  const text = allPayloads.map((p) =>
                    `[${p.segment_label || p.segment_type}] (${p.duration}s)\n${p.visual_prompt}\n---`
                  ).join('\n\n');
                  navigator.clipboard.writeText(text);
                }}
              >
                <Copy className="h-3 w-3" />
                复制全部提示词
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-1.5 rounded-xl border border-[#EBEAE6] bg-[#FAFAF9]/50 px-3 py-2 text-[11px] text-[#6E6E73] hover:border-[#D1CFC8] hover:text-[#1C1C1E] transition-colors"
                onClick={() => {
                  const json = JSON.stringify(allPayloads.map((p) => p.api_payload), null, 2);
                  const blob = new Blob([json], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = 'structforge-flux-payloads.json';
                  a.click(); URL.revokeObjectURL(url);
                }}
              >
                <Download className="h-3 w-3" />
                导出 Flux JSON
              </button>
            </div>
          </div>
        )}
      </div>
    </Drawer>
  );
}

function PayloadDetail({ payload }: { payload: BlueprintSegmentPayload }) {
  return (
    <div className="space-y-4 rounded-xl bg-[#FAFAF9] ring-1 ring-[#EBEAE6]/50 p-4">
      {/* Segment info */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="rounded-full bg-[#FAFAF9] px-2 py-0.5 text-[10px] uppercase tracking-wider font-bold text-[#C8843C] ring-1 ring-[#EBEAE6]">
            {TYPE_LABELS[payload.segment_type] ?? payload.segment_type}
          </span>
          <span className="text-xs text-slate-500">
            {payload.segment_label} · {payload.duration.toFixed(1)}s
          </span>
        </div>
        <p className="text-sm text-slate-200 leading-relaxed">
          {payload.visual_prompt || payload.script_text || '(无视觉描述)'}
        </p>
      </div>

      {/* Production params */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <span className="text-slate-500">运镜</span>
          <p className="font-mono text-slate-400">
            {CAMERA_LABELS[payload.camera] ?? payload.camera}
          </p>
        </div>
        <div>
          <span className="text-slate-500">特效</span>
          <p className="font-mono text-slate-400">
            {FX_LABELS[payload.visual_fx] ?? payload.visual_fx}
          </p>
        </div>
        <div>
          <span className="text-slate-500">节奏</span>
          <p className="font-mono text-slate-400">{payload.pace}</p>
        </div>
        <div>
          <span className="text-slate-500">情绪</span>
          <p className="font-mono text-slate-400">{payload.emotion}</p>
        </div>
      </div>

      {/* Cost & tokens — refined billing style */}
      <div className="flex items-center justify-between pt-2 border-t border-[#EBEAE6]00 text-xs">
        <div className="flex items-center gap-1 text-slate-500">
          <Cpu className="h-3.5 w-3.5" />
          Tokens:
        </div>
        <span className="font-mono text-slate-200">
          ~{payload.estimated_tokens}
        </span>
        <div className="flex items-center gap-1 ml-4 text-slate-500">
          <DollarSign className="h-3.5 w-3.5" />
          Cost:
        </div>
        <span className="font-mono text-emerald-400">
          ${payload.estimated_cost_usd.toFixed(3)}
        </span>
      </div>

      {/* ── Code block: full API payload ── */}
      <div className="flex-1 flex flex-col space-y-2">
        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Code2 className="h-3.5 w-3.5" />
          API 请求体 (RunningHub Flux)
        </h4>
        <div className="flex-1 bg-[#FAFAF9]50 rounded-xl border border-[#EBEAE6]00 p-4 overflow-y-auto">
          <pre className="text-[11px] font-mono leading-relaxed text-emerald-400/90">
{JSON.stringify(payload.api_payload, null, 2)}</pre>
        </div>
      </div>

      {/* Hint */}
      <p className="text-[10px] text-text-muted leading-relaxed">
        {payload.is_available
          ? '↑ 点击底部「一键渲染」按钮，系统将提交此 Payload 至 RunningHub Flux，生成真实视频替换蓝图卡。'
          : '↑ 以上请求体会在填入 Flux API Key 后自动发送。当前模式下，该分镜渲染为静态蓝图卡，音频（TTS · BGM）保持完整。'}
        {' '}此 Payload 结构同样兼容 Sora / Runway / Kling — 切换底层模型只需修改 model 字段。
      </p>
    </div>
  );
}
