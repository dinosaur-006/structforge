import { useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';

const ITEMS = [
  { q: 'StructForge 是什么？', a: 'AI 驱动的爆款视频结构迁移引擎。从参考视频中提取经过验证的结构骨架，应用到你的产品上，生成包含钩子、痛点、产品展示、信任背书和行动号召的新视频方案。' },
  { q: '如何使用？', a: '上传参考视频 → AI 提取结构 → 输入产品信息 → 生成脚本 → 审核调整 → 渲染成片。每个分镜都标注了素材来源和生成方式。' },
  { q: '需要 API Key 吗？', a: 'LLM 的 API Key 是必需的，用于视频结构分析和脚本生成。ComfyUI RunningHub Key 是可选的，用于 AI 图片生成和视频生成。Edge TTS 语音合成完全免费，无需任何 Key。' },
  { q: '支持哪些 AI 模型？', a: 'LLM：豆包 Seed、通义 Qwen、DeepSeek、OpenAI、智谱 GLM、Moonshot、Ollama 本地模型。图片生成：ComfyUI Flux。视频生成：RunningHub WAN 2.2。语音合成：Edge TTS（免费）。' },
  { q: '如何提升视频质量？', a: '上传清晰的产品图片（AI 会分析外观用于生成）。填写详细的产品信息和卖点。选择合适的脚本风格（高质感/高点击等）。确保 RunningHub ComfyUI 已配置以启用 AI 图片生成。' },
  { q: '生成失败怎么办？', a: '在设置页测试 LLM 连接。确认 FFmpeg 已安装。ComfyUI 不可用时自动回退到提示词卡片——视频永远不会渲染失败。' },
];

export default function FAQPanel() {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [allOpen, setAllOpen] = useState(false);
  const toggle = (i: number) => setExpanded(p => ({ ...p, [i]: !p[i] }));
  const toggleAll = () => { if (allOpen) { setExpanded({}); } else { const a: Record<number, boolean> = {}; ITEMS.forEach((_, i) => a[i] = true); setExpanded(a); } setAllOpen(!allOpen); };

  return (
    <div className="text-[#6E6E73]">
      <div className="flex items-center justify-between mb-2 px-1.5">
        <span className="text-[11px] font-medium text-[#1C1C1E]">常见问题</span>
        <button onClick={toggleAll} className="text-[10px] text-[#AEAEB2] hover:text-[#6E6E73] transition-colors">{allOpen ? '收起' : '展开'}</button>
      </div>
      <div className="space-y-px">
        {ITEMS.map((item, i) => (
          <div key={i}>
            <button onClick={() => toggle(i)} className="w-full flex items-center gap-1.5 py-1.5 px-1.5 text-left text-[11px] text-[#6E6E73] hover:text-[#1C1C1E] rounded-md hover:bg-[#FAFAF9] transition-colors">
              {expanded[i] ? <ChevronDown className="w-3 h-3 flex-shrink-0 text-[#C8843C]/60" /> : <ChevronRight className="w-3 h-3 flex-shrink-0" />}
              <span className="leading-snug">{item.q}</span>
            </button>
            {expanded[i] && <p className="pb-2 pl-6 pr-1.5 text-[10px] leading-relaxed text-[#AEAEB2]">{item.a}</p>}
          </div>
        ))}
      </div>
      <a href="https://github.com/dinosaur-006/structforge" target="_blank" rel="noopener" className="flex items-center gap-1 mt-2 px-1.5 text-[10px] text-[#AEAEB2] hover:text-[#C8843C] transition-colors"><ExternalLink className="w-2.5 h-2.5" /> GitHub</a>
    </div>
  );
}
