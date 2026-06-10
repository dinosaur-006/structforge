import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react';

interface CapInfo { state: string; label: string; detail: string; }

const GLYPHS: Record<string, string> = { llm: 'LLM', vision: 'VIS', asr: 'ASR', aigc: 'IMG', videoGeneration: 'VID', taskExecution: 'TSK' };

export default function SettingsPage() {
  const [caps, setCaps] = useState<Record<string, CapInfo> | null>(null);
  const [llmStatus, setLlmStatus] = useState<{ status: string; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => { api.getCapabilities().then(setCaps).catch(() => {}); }, []);

  const testLLM = async () => {
    setTesting(true); setLlmStatus(null);
    try {
      const r = await (await fetch('/api/v1/diagnostics/llm')).json();
      setLlmStatus({
        status: r.status,
        message: r.status === 'healthy' ? `Connected · ${r.model} · ${r.latency_seconds}s`
          : r.status === 'timeout' ? `Timeout · ${r.latency_seconds}s limit: ${r.timeout_seconds}s`
          : r.message || 'Error',
      });
    } catch (e: any) { setLlmStatus({ status: 'error', message: e.message }); }
    finally { setTesting(false); }
  };

  const services = caps ? [
    { key: 'llm', detail: caps.llm?.detail || '', state: caps.llm?.state || 'unknown' },
    { key: 'vision', detail: caps.vision?.detail || '', state: caps.vision?.state || 'unknown' },
    { key: 'asr', detail: caps.asr?.detail || '', state: caps.asr?.state || 'unknown' },
    { key: 'aigc', detail: caps.aigc?.detail || '', state: caps.aigc?.state || 'unknown' },
    { key: 'videoGeneration', detail: caps.videoGeneration?.detail || '', state: caps.videoGeneration?.state || 'unknown' },
    { key: 'taskExecution', detail: caps.taskExecution?.detail || '', state: caps.taskExecution?.state || 'unknown' },
  ] : [];

  const envVars = [
    { v: 'STRUCTFORGE_DOUBAO_LLM_API_KEY', d: 'LLM API Key', r: true },
    { v: 'STRUCTFORGE_DOUBAO_LLM_ENDPOINT', d: 'LLM Endpoint', r: true },
    { v: 'STRUCTFORGE_DOUBAO_LLM_MODEL', d: 'LLM Model', r: false },
    { v: 'STRUCTFORGE_RUNNINGHUB_API_KEY', d: 'ComfyUI / RunningHub', r: false },
    { v: 'STRUCTFORGE_VOLCANO_ASR_API_KEY', d: 'ASR API Key', r: false },
    { v: 'STRUCTFORGE_TTS_API_KEY', d: 'TTS API Key (Edge TTS free)', r: false },
    { v: 'STRUCTFORGE_DOUBAO_IMAGE_API_KEY', d: 'Image Gen API Key', r: false },
    { v: 'STRUCTFORGE_CELERY_TASK_ALWAYS_EAGER', d: 'Tasks inline (dev=true)', r: false },
    { v: 'STRUCTFORGE_CONTENT_SAFETY_ENABLED', d: 'Content safety check (default false)', r: false },
    { v: 'STRUCTFORGE_CONTENT_SAFETY_BLOCKED_TERMS', d: 'Blocked terms (comma-sep)', r: false },
  ];

  return (
    <div>
      <section className="mx-auto max-w-[1240px] px-5 sm:px-6 lg:px-8 py-8 sm:py-12 lg:py-14">
        <header className="mb-8">
          <p className="text-xs tracking-[0.15em] text-[#C8843C]/70 font-medium mb-2">系统配置</p>
          <h1 className="text-[28px] sm:text-[34px] font-semibold tracking-tight text-[#1C1C1E]">系统设置</h1>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-10">
          {/* Service status */}
          <div className="lg:col-span-2 rounded-xl bg-white border border-[#EBEAE6] shadow-[0_1px_3px_rgba(0,0,0,0.02)] p-5 sm:p-6">
            <h2 className="text-sm font-medium text-[#1C1C1E] mb-5">服务状态</h2>
            {!caps ? (
              <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-10 bg-[#FAFAF9] rounded-xl animate-pulse" />)}</div>
            ) : (
              <div className="space-y-0.5">
                {services.map(svc => (
                  <div key={svc.key} className="flex items-center gap-4 px-3 py-2.5 rounded-xl hover:bg-[#FAFAF9] transition-colors">
                    <span className="text-[10px] font-medium text-[#AEAEB2] w-8">{GLYPHS[svc.key] || svc.key}</span>
                    <div className="flex-1 min-w-0"><p className="text-[13px] text-[#6E6E73] truncate">{svc.detail}</p></div>
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{
                      backgroundColor: svc.state === 'configured' ? '#4A9E7C' : svc.state === 'fallback' ? '#C8843C' : '#D1CFC8'
                    }} />
                    <span className="text-[11px] font-medium" style={{
                      color: svc.state === 'configured' ? '#4A9E7C' : svc.state === 'fallback' ? '#C8843C' : '#AEAEB2'
                    }}>{svc.state === 'configured' ? '已启用' : svc.state === 'fallback' ? '回退' : '未启用'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* LLM test */}
          <div className="rounded-xl bg-white border border-[#EBEAE6] shadow-[0_1px_3px_rgba(0,0,0,0.02)] p-5 sm:p-6 flex flex-col">
            <h2 className="text-sm font-medium text-[#1C1C1E] mb-4">连接测试</h2>
            <button onClick={testLLM} disabled={testing}
              className="w-full flex items-center justify-center gap-2 py-2.5 text-[13px] font-medium rounded-xl border border-[#EBEAE6] hover:border-[#D1CFC8] hover:bg-[#FAFAF9] text-[#1C1C1E] disabled:opacity-50 transition-all"
            >{testing ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 测试中…</> : 'Ping LLM 端点'}</button>
            {llmStatus && (
              <div className={`mt-3 p-3 rounded-xl text-[12px] ${
                llmStatus.status === 'healthy' ? 'bg-[#F2F8F4] text-[#4A9E7C]' :
                llmStatus.status === 'timeout' ? 'bg-[#FDF6EE] text-[#C8843C]' :
                'bg-[#FDF4F4] text-[#D45A5A]'
              }`}>
                <div className="flex items-center gap-1.5 mb-1 font-medium">
                  {llmStatus.status === 'healthy' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                  {llmStatus.status}
                </div>
                <p className="text-[11px] opacity-80">{llmStatus.message}</p>
              </div>
            )}
            <div className="flex-1" />
            <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noopener"
              className="flex items-center gap-1.5 mt-4 text-[11px] text-[#AEAEB2] hover:text-[#6E6E73] transition-colors">
              <ExternalLink className="w-3 h-3" /> API 文档
            </a>
          </div>
        </div>

        {/* Env vars */}
        <section>
          <h2 className="text-sm font-medium text-[#1C1C1E] mb-4">环境变量</h2>
          <div className="rounded-xl bg-white border border-[#EBEAE6] shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">
            {envVars.map(({ v, d, r }) => (
              <div key={v} className="flex items-center gap-4 px-5 py-3 border-b border-[#F2F0ED] last:border-b-0 hover:bg-[#FAFAF9] transition-colors">
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: r ? '#C8843C' : '#D1CFC8' }} />
                <code className="text-[12px] text-[#6E6E73] font-medium truncate">{v}</code>
                <span className="text-[11px] text-[#AEAEB2] flex-shrink-0">{d}</span>
                <span className="text-[10px] text-[#D1CFC8] ml-auto flex-shrink-0">{r ? '必填' : '可选'}</span>
              </div>
            ))}
          </div>
        </section>

        <footer className="mt-10 pt-5 border-t border-[#EBEAE6] flex items-center justify-between text-[11px] text-[#AEAEB2]">
          <span>StructForge v0.2.0</span>
          <span>Doubao LLM · RunningHub ComfyUI · Edge TTS</span>
        </footer>
      </section>
    </div>
  );
}
