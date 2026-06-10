# StructForge → Pixelle-Video 视频生成逻辑迁移方案

> 日期: 2026-06-09  
> 问题: "可以将我现在这个产品最终生成视频的逻辑改为 Pixelle-Video 的生成视频逻辑吗"  
> 结论: **可以且应该改，但不能照搬 — 需要"嫁接"而非"替换"**

---

## 目录

1. [核心判断](#1-核心判断)
2. [两套系统的本质差异](#2-两套系统的本质差异)
3. [StructForge 当前渲染流程的 7 个致命问题](#3-structforge-当前渲染流程的-7-个致命问题)
4. [Pixelle-Video 逻辑中可直接嫁接的部分](#4-pixelle-video-逻辑中可直接嫁接的部分)
5. [Pixelle-Video 逻辑中需要适配的部分](#5-pixelle-video-逻辑中需要适配的部分)
6. [Pixelle-Video 逻辑中不能采用的部分](#6-pixelle-video-逻辑中不能采用的部分)
7. [详细改造方案 (Step by Step)](#7-详细改造方案)
8. [代码级实现路径](#8-代码级实现路径)
9. [验收标准](#9-验收标准)

---

## 1. 核心判断

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   Pixelle-Video 的生成逻辑能成功，核心在于 3 个设计决策:      │
│                                                              │
│   ① TTS先于视频 — 音频时长决定视频时长（杜绝音画不同步）     │
│   ② FrameProcessor统一入口 — 每帧4步，无分支遗漏             │
│   ③ HTML模板作为主要渲染方式 — 不依赖外部素材是否可用         │
│                                                              │
│   这三个决策是"架构真理"，不依赖具体业务场景。                │
│   StructForge 完全可以且应该采纳。                            │
│                                                              │
│   但 Pixelle-Video 的"纯AI生成"假设与 StructForge 的         │
│   "素材匹配+结构迁移"场景有本质冲突，需要适配而非照搬。       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 结论矩阵

| Pixelle-Video 组件 | 可直接采用? | 需要适配? | 不可采用? |
|------|:---:|:---:|:---:|
| LinearVideoPipeline (Template Method) | | ✅ | |
| PipelineContext (统一状态) | | ✅ | |
| TTS驱动时长 | ✅ | | |
| FrameProcessor (每帧4步) | | ✅ | |
| HTMLFrameGenerator (模板渲染) | | ✅ | |
| VideoService (FFmpeg合成) | | ✅ | |
| ProgressEvent (进度回调) | ✅ | | |
| MediaService (ComfyUI生图) | | | ❌ |
| LLM生成旁白 | | | ❌ |
| pure文本→视频 | | | ❌ |

---

## 2. 两套系统的本质差异

### 2.1 核心流程对比

```
Pixelle-Video 流程:
  文本输入 → LLM生成旁白 → LLM生成图片提示词 → ComfyUI生图
  → TTS生成音频 → HTML合成帧 → 图片+音频→视频段 → 拼接+BGM → 最终MP4

StructForge 流程:
  参考视频+产品信息 → LLM生成分镜脚本(FinalScript)
  → 素材匹配(gap_detector) → 素材补全(gap_filler)
  → [用户审核 ReviewPanel] → 触发渲染
  → 每分镜: 判断素材类型 → 决定渲染方式(原视频/用户图片/包装卡/AI提示词卡)
  → TTS合成 → 音频合并 → 拼接+BGM → 最终MP4
```

### 2.2 关键差异表

| 维度 | Pixelle-Video | StructForge |
|------|------|------|
| **素材来源** | 100% AI 生成 (ComfyUI/API) | 混合: 原视频片段 + 用户上传 + AI补全 |
| **分镜创建** | LLM 从主题实时生成 | LLM 从参考视频结构迁移 |
| **每帧画面** | 图片提示词→ComfyUI→图片 | 按素材类型决策: 原视频/图片/卡片 |
| **时长决策** | TTS音频时长 → 视频时长 | 结构模板时长 → 视频时长 → TTS |
| **渲染核心** | HTML 模板 (Playwright) | FFmpeg 滤镜链 (drawtext + ASS 字幕) |
| **失败处理** | 无处可失败 (AI总会产出) | 多级回退 (原视频→卡片→黑屏) |
| **用户控制** | 无 (全自动) | ReviewPanel 审核+切换来源 |

### 2.3 根本矛盾

> Pixelle-Video 假设**每帧都需要AI生成**，StructForge 假设**有些帧已有素材、有些没有**。

这导致了 StructForge compositor.py 的 600+行 if/else 分支地狱。而 Pixelle-Video 的 FrameProcessor 只有 4 个干净的步骤。

---

## 3. StructForge 当前渲染流程的 7 个致命问题

### 问题 1: TTS 在视频段生成之后才合成

```
当前流程:
  1. 创建视频段 (用 null audio)
  2. 生成 TTS 音频
  3. 用 ffmpeg 把 TTS 音频混入视频段 (merge_audio_video_smart)

问题:
  - 视频段的时长是"估算的"而非"实际的"
  - 如果 TTS 音频比视频段长 → 需要 tpad 冻结最后一帧 (卡顿)
  - 如果 TTS 音频比视频段短 → 视频末尾有静音段
  - "TTS 驱动时长"只是事后补救(patch)，不是架构级别
```

### 问题 2: 每帧渲染逻辑散落在 400+ 行 if/else 中

```
compositor.py 的 _process_segments():
  ├─ if source_path is None:         # 无素材分支 (200行)
  │   ├─ if packaging: ...
  │   └─ else (aigc): ...
  ├─ elif asset["type"] == "image":  # 图片分支 (30行)
  └─ else:                           # 视频分支 (150行)
      ├─ if aigc segment → skip ref → prompt card
      ├─ if reference → shot pool match
      ├─ if no shot → AI video gen → PromptCard → packaging fallback
      └─ else → normal video command

每个分支都有细微不同的参数传递、错误处理和警告生成。
```

### 问题 3: 时长体系不一致

```
当前:
  segment.duration (来自 FinalScript, LLM 估计的)
    → _output_duration() (版本微调)
      → build_image_command(-t duration) / build_video_command(-t duration)
        → [事后] TTS 合成
          → _probe_duration(tts) → segment.duration = actual
            → _reflow_timeline (事后修正 start/end)

问题: duration 被多次覆写，start/end 在渲染过程中不一致。
```

### 问题 4: 视频段和音频的"先有鸡还是先有蛋"

```
当前:
  1. 没有音频 → 创建视频段 (用 anullsrc 静音)
  2. 生成音频
  3. merge_audio_video_smart() 把音频合入视频

Pixelle-Video:
  1. 生成音频 → 获取时长
  2. 用音频时长创建视频段 (t=audio_duration)
  3. 一步完成: ffmpeg -loop 1 -i image -i audio -t audio_duration output.mp4
```

### 问题 5: 渲染策略分散在 compositor.py 和 render_pipeline.py 两处

```
当前存在两套渲染代码:
  - compositor.py:     600+ 行 (旧代码, 仍被直接调用)
  - render_pipeline.py: 650+ 行 (新代码, 部分功能未完整)

两个文件有大量重复代码:
  - _ass_for_segment
  - build_image_command / build_video_command / build_placeholder_command
  - _cinematic_motion / _apply_visual_fx / _version_filters
  - _merge_video_audio_smart
  - _has_audio_stream / _probe_duration / _run
```

### 问题 6: 没有统一的"Per-Segment"处理抽象

Pixelle-Video 有 `FrameProcessor` — 任何帧进入，经过4步处理，产出视频段。

StructForge 没有等价物 — 每段根据素材类型走不同的 if/else 分支，每个分支有不同的处理逻辑。

### 问题 7: 进度上报粗糙

```
当前: polling-based (前端每1秒查询一次)
Pixelle-Video: callback-based (精确到每帧的4个子步骤)
```

---

## 4. Pixelle-Video 逻辑中可直接嫁接的部分

### 4.1 TTS 驱动时长的完整实现

**Pixelle-Video 做法** (FrameProcessor._step_generate_audio → _step_create_video_segment):

```python
# Step 1: TTS first
audio_path = await tts(text=frame.narration, ...)
frame.audio_path = audio_path
frame.duration = probe_audio_duration(audio_path)  # ← 关键

# Step 4: Video segment uses audio duration
ffmpeg -loop 1 -i image.png -i audio.mp3 \
       -t {frame.duration} \    # ← 用音频时长!
       -c:v libx264 -c:a aac output.mp4
```

**StructForge 改造**: 修改 `_synthesize_speech` 从 Step 3 提前到 Step 2 之前。每段先生成 TTS → 用实际音频时长作为视频段时长 → 创建视频段时直接合入音频。

### 4.2 统一的 SegmentProcessor

**Pixelle-Video 做法**: FrameProcessor 统一处理所有帧:

```python
class FrameProcessor:
    async def __call__(self, frame, storyboard, config):
        await self._step_generate_audio(frame, config)
        await self._step_generate_media(frame, config)      # 可能需要/跳过
        await self._step_compose_frame(frame, storyboard, config)
        await self._step_create_video_segment(frame, config)
        return frame
```

**StructForge 改造**: 创建 `SegmentProcessor`:

```python
class SegmentProcessor:
    async def __call__(self, segment, ctx, config):
        await self._step_resolve_source(segment, ctx)        # 确定素材来源
        await self._step_generate_tts(segment, ctx, config)   # TTS 先于视频
        await self._step_render_visual(segment, ctx, config)  # 渲染画面
        await self._step_assemble_segment(segment, ctx, config) # 画面+音频→MP4
        return segment
```

### 4.3 HTML 模板作为主要渲染方式

**Pixelle-Video 做法**: **所有帧**都通过 Playwright 渲染 HTML 模板生成 PNG，然后 PNG→视频。

**StructForge 现状**: `_render_prompt_card_html` 只用于 AI 提示词卡片，其余用 Pillow/ASS 字幕。

**StructForge 改造**: 
- 已有 `ai-services/templates/prompt_card.html` — 可以直接扩展为通用模板
- 创建 `ai-services/templates/segment_default.html` — 统一的 1080x1920 分镜模板
- 模板变量: `{{segment_type}}`, `{{script_text}}`, `{{visual_bg}}`, `{{camera_hint}}`
- 所有分镜都先通过模板渲染为 PNG，然后 `-loop 1` + 音频 → 视频段

### 4.4 VideoService 的完整合并逻辑

**Pixelle-Video 的 VideoService.merge_audio_video()** 已经非常完善:

```python
def merge_audio_video(video, audio, output, replace_audio=True,
                      pad_strategy="freeze", auto_adjust_duration=True):
    # 自动处理: 视频<音频 → 冻结延展 / 视频>音频(超出容差) → 裁剪
    # 自动检测: 视频是否有音频轨道
    # 支持: 替换音频 / 混合音频
```

**StructForge 现状**: `_merge_video_audio_smart()` 已经移植了这个逻辑，但使用方式不对 — 它是事后补救，不是架构级集成。

### 4.5 ProgressEvent 回调链

**Pixelle-Video 做法**:

```python
progress_callback(ProgressEvent(
    event_type="frame_step",
    progress=0.45,
    frame_current=3, frame_total=5,
    step=2,                # 1=audio, 2=media, 3=compose, 4=video
    action="media"
))
```

**StructForge 改造**: 用 SSE 替代 polling，每个 SegmentProcessor 步骤发送 ProgressEvent。

---

## 5. Pixelle-Video 逻辑中需要适配的部分

### 5.1 素材来源解析 (替代 _step_generate_media)

Pixelle-Video 的 `_step_generate_media` 总是调用 ComfyUI 生图。StructForge 需要的是 "素材路由" 逻辑:

```python
# StructForge 的 SegmentProcessor._step_resolve_source()
async def _step_resolve_source(self, segment, ctx):
    """决定本段的素材来源 — 这是 StructForge 独有的逻辑"""
    asset = ctx.assets.get(segment.asset_id)

    if not asset or not asset.get("file_path"):
        # 无素材 → AI 提示词卡片 (类似 Pixelle-Video 的生图)
        segment.render_mode = "prompt_card"
        segment.visual_source = await self._generate_prompt_card(segment, ctx)
    elif asset["type"] == "image":
        segment.render_mode = "image"
        segment.visual_source = Path(asset["file_path"])
    elif asset["type"] == "video":
        analysis = asset.get("analysis") or {}
        if analysis.get("reference_source"):
            # 参考视频 → 检查场景匹配
            segment.render_mode = "reference_clip"
            segment.visual_source = self._find_best_clip(segment, asset)
        else:
            segment.render_mode = "user_video"
            segment.visual_source = Path(asset["file_path"])
```

这与 Pixelle-Video 的 `_step_generate_media` 同位置但不同逻辑。

### 5.2 视频段组装 (适配多种 render_mode)

Pixelle-Video 只有两种:
- `media_type == "video"` → overlay + audio
- `media_type == "image"` 或 `None` → image→video + audio

StructForge 需要处理:
- `render_mode == "user_video"` → 裁剪+字幕叠加+音频替换
- `render_mode == "image"` → 图片→视频+运镜+字幕+音频
- `render_mode == "prompt_card"` → HTML渲染→PNG→视频+音频
- `render_mode == "reference_clip"` → 参考视频片段+字幕叠加+静音+音频

```python
async def _step_assemble_segment(self, segment, ctx, config):
    if segment.render_mode == "user_video":
        return self._assemble_video_segment(segment, ctx, config)
    elif segment.render_mode == "image":
        return self._assemble_image_segment(segment, ctx, config)
    elif segment.render_mode == "prompt_card":
        return self._assemble_card_segment(segment, ctx, config)
    elif segment.render_mode == "reference_clip":
        return self._assemble_reference_segment(segment, ctx, config)
```

### 5.3 PipelineContext 适配

Pixelle-Video 的 PipelineContext 侧重"创作"，StructForge 需要侧重"迁移":

```python
@dataclass
class StructForgeRenderContext:
    # === Pixelle-Video 相同字段 ===
    task_id: str
    task_dir: Path
    segments: list[SegmentContext]          # 替代 frames
    final_video_path: Optional[str]

    # === StructForge 独有字段 ===
    job_id: str
    project_id: str
    script: FinalScript
    assets: dict[str, dict]                # 素材库
    version: str                           # 渲染版本
    resolution: tuple[int, int]
    warnings: list[str]
    self_audit: Optional[dict]

    # === Pixelle-Video 不需要的 ===
    # (narrations, image_prompts 等在 LLM 脚本生成阶段已确定)
```

---

## 6. Pixelle-Video 逻辑中不能采用的部分

### 6.1 ComfyKit/ComfyUI 媒体生成

**原因**: StructForge 不使用 ComfyUI。图片/视频生成通过 API 调用 (Seedance, Runway, Kling) 或 Pillow 本地渲染。

**处理方式**: `_step_generate_media` 在 StructForge 中被替换为 `_step_resolve_source`（素材路由），AI 生成部分通过 `AIVideoService` 调用。

### 6.2 LLM 实时生成旁白/图片提示词

**原因**: StructForge 的脚本在 `migrator.py` 阶段已由 LLM 生成完成（FinalScript + FinalSegment），渲染阶段不需要再次调用 LLM。

**处理方式**: 保留 `migrator.py` 的 LLM 调用逻辑不变，渲染阶段只读取已生成的脚本。

### 6.3 纯文本→视频 的 StandardPipeline 流程

**原因**: StructForge 的核心价值是"结构迁移"而非"主题生成"。输入不是主题文本，而是参考视频+产品信息。

**处理方式**: 保留 `MigratorService.generate()` 的完整逻辑不变。只改造渲染阶段 (compositor.py / render_pipeline.py)。

---

## 7. 详细改造方案

### 7.1 整体架构变更

```
当前架构:
  MigratorService.generate()
    → FinalScript (含 segments + metadata)
    → ReviewPanel (用户审核)
    → Compositor.render() / VideoRenderPipeline.run()
      → [400行 if/else 每段处理]
      → [事后 TTS]
      → [拼接]
      → [BGM]

改造后架构:
  MigratorService.generate()              ← 不变
    → FinalScript
    → ReviewPanel                         ← 不变
    → StructForgeRenderPipeline.run()     ← 重构
      ├─ Step 1: _prepare                 ← 保留，微调
      ├─ Step 2: _synthesize_all_tts      ← 提前! (原 Step 3)
      ├─ Step 3: _process_segments        ← 重构 (用 SegmentProcessor)
      │   └─ SegmentProcessor.__call__() × N
      │       ├─ _step_resolve_source     ← 素材路由
      │       ├─ _step_render_visual      ← HTML模板渲染
      │       └─ _step_assemble_segment   ← 画面+音频→MP4
      ├─ Step 4: _assemble_video          ← 保留
      ├─ Step 5: _mix_bgm                 ← 保留
      └─ Step 6: _finalize                ← 保留
```

**关键变化**: TTS 从 Step 3 提前到 Step 2。每个分镜的视觉渲染使用 **HTML 模板** 作为统一入口。

### 7.2 新增文件清单

| 文件 | 作用 | 参考 Pixelle-Video 文件 |
|------|------|------|
| `ai-services/services/segment_processor.py` | 每段统一处理 (替代 if/else) | `services/frame_processor.py` |
| `ai-services/services/render_context.py` | 移出 render_pipeline.py 的 RenderContext | `pipelines/linear.py` 的 PipelineContext |
| `ai-services/services/segment_assembler.py` | 按 render_mode 组装视频段 | `services/video.py` (部分) |
| `ai-services/services/html_frame.py` | 通用 HTML→PNG 渲染 (已有 frame_renderer.py 可合并) | `services/frame_html.py` |
| `ai-services/templates/segment_default.html` | 通用分镜 HTML 模板 | `templates/1080x1920/default.html` |

### 7.3 修改文件清单

| 文件 | 改动范围 | 描述 |
|------|------|------|
| `ai-services/services/render_pipeline.py` | 重度重构 | 7步→6步，TTS提前，SegmentProcessor集成 |
| `ai-services/services/compositor.py` | 大幅简化 | 删除 if/else 分支，保留 FFmpeg 命令构建函数 |
| `ai-services/services/tts_engine.py` | 微调 | 增加批量 TTS 方法 (一次性为所有段合成) |

### 7.4 删除/合并

| 文件 | 操作 |
|------|------|
| `ai-services/services/blueprint_renderer.py` | 合并到 `html_frame.py` |
| `ai-services/services/frame_renderer.py` | 合并到 `html_frame.py` |

---

## 8. 代码级实现路径

### Phase 1: TTS 驱动时长 (核心架构改造)

**目标**: 将 TTS 从 "事后补救" 改为 "架构前提"。

**修改 `render_pipeline.py`**:

```python
class VideoRenderPipeline:
    def run(self, ...):
        # OLD order:
        # _prepare → _process_segments → _synthesize_speech → _apply_overlays → ...

        # NEW order:
        self._prepare(ctx)
        self._synthesize_all_tts(ctx)       # ← MOVED HERE (before segments!)
        self._process_segments(ctx)          # Now uses actual TTS durations
        self._apply_overlays(ctx)
        self._assemble_video(ctx)
        self._mix_audio(ctx)
        self._finalize(ctx)
```

**修改 `_synthesize_all_tts`** (原 `_synthesize_speech`):

```python
def _synthesize_all_tts(self, ctx):
    """批量 TTS 合成 — 在创建视频段之前运行。
    每个分镜的实际时长由 TTS 音频决定，而非 LLM 估算。
    """
    for idx, segment in enumerate(ctx.segments):
        seg_text = _clean_script(segment.script)
        if not seg_text.strip():
            segment.tts_path = None
            continue

        tts_path = ctx.work_dir / f"segment_{idx:03d}_tts.mp3"
        if tts.synthesize(seg_text, tts_path, target_duration=segment.duration):
            actual_dur = _probe_duration(tts_path)
            # KEY: 用 TTS 实际时长覆写 LLM 估算的时长
            segment.duration = max(actual_dur, 0.5)
            segment.tts_path = tts_path
        else:
            segment.tts_path = None

    # 重排时间线
    cursor = 0.0
    for seg in ctx.segments:
        seg.start = cursor
        seg.end = cursor + seg.duration
        cursor = seg.end
```

**修改 `_process_segments`**:

```python
def _process_segments(self, ctx):
    """每段: 渲染画面 + 直接合入已有 TTS 音频 → 视频段"""
    for idx, segment in enumerate(ctx.segments):
        seg_path = ctx.work_dir / f"segment_{idx:03d}.mp4"

        # 渲染画面 (图片/卡片/视频片段)
        visual_input = self._render_segment_visual(segment, ctx, idx)

        if segment.tts_path and Path(segment.tts_path).exists():
            # KEY: 直接用 TTS 音频创建视频段 (Pixelle-Video 模式)
            self._create_video_with_audio(
                visual_input, segment.tts_path, seg_path,
                duration=segment.duration,
                width=ctx.width, height=ctx.height,
            )
        else:
            # 无 TTS → 保留原音频或用静音
            self._create_video_silent(
                visual_input, seg_path,
                duration=segment.duration,
                width=ctx.width, height=ctx.height,
            )

        ctx.segment_files.append(seg_path)
```

### Phase 2: SegmentProcessor (统一处理抽象)

**新建 `ai-services/services/segment_processor.py`**:

```python
"""Segment processor — unified per-segment pipeline.
Pattern borrowed from Pixelle-Video's FrameProcessor.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class SegmentContext:
    """Per-segment state, analogous to Pixelle-Video's StoryboardFrame."""
    index: int
    segment: Any                      # FinalSegment (Pydantic model fragment)
    render_mode: str = ""             # "user_video" | "image" | "prompt_card" | "reference_clip"
    visual_input: Optional[Path] = None  # 渲染好的画面 PNG
    tts_path: Optional[Path] = None
    video_segment_path: Optional[Path] = None
    duration: float = 0.0
    warnings: list[str] = field(default_factory=list)


class SegmentProcessor:
    """Process a single segment through the unified 3-step pipeline.
    
    Unlike Pixelle-Video's FrameProcessor which always generates images,
    this first resolves the source type, then renders based on mode.
    """
    
    def __init__(self, settings, assets: dict):
        self.settings = settings
        self.assets = assets
    
    def process(self, ctx: SegmentContext, render_ctx) -> SegmentContext:
        """Execute the 3-step segment pipeline."""
        # Step 1: Resolve source → determine render_mode
        self._step_resolve_source(ctx, render_ctx)
        
        # Step 2: Render visual based on mode
        self._step_render_visual(ctx, render_ctx)
        
        # Step 3: Assemble MP4 segment (visual + audio)
        self._step_assemble(ctx, render_ctx)
        
        return ctx
    
    def _step_resolve_source(self, ctx: SegmentContext, rctx) -> None:
        """Determine where this segment's visual comes from.
        
        This is StructForge's equivalent of Pixelle-Video's _step_generate_media,
        but instead of always calling ComfyUI, it routes to different sources.
        """
        seg = ctx.segment
        asset = self.assets.get(seg.asset_id) if seg.asset_id else None
        source_path = Path(asset["file_path"]) if asset and asset.get("file_path") else None
        
        if source_path is None or not source_path.exists():
            ctx.render_mode = "prompt_card"
        elif asset["type"] == "image":
            ctx.render_mode = "image"
            ctx.visual_input = source_path
        elif asset["type"] == "video":
            analysis = asset.get("analysis") or {}
            seg_source = getattr(seg, 'source', 'original') or 'original'
            if analysis.get("reference_source") and seg_source in ("aigc", "packaging"):
                ctx.render_mode = "prompt_card"  # aigc segments skip reference
            elif analysis.get("reference_source"):
                ctx.render_mode = "reference_clip"
            else:
                ctx.render_mode = "user_video"
            ctx.visual_input = source_path
        
        log.info(f"Segment {ctx.index}: render_mode={ctx.render_mode}")
    
    def _step_render_visual(self, ctx: SegmentContext, rctx) -> None:
        """Render the segment's visual frame.
        
        All non-video modes produce a PNG image as intermediate output.
        This is Pixelle-Video's HTML compose step adapted for StructForge.
        """
        seg = ctx.segment
        
        if ctx.render_mode == "prompt_card":
            # Generate AI prompt card → always produces a PNG
            card_path = rctx.work_dir / f"segment_{ctx.index:03d}_promptcard.png"
            self._render_prompt_card(seg, card_path, rctx)
            ctx.visual_input = card_path
            
        elif ctx.render_mode == "image":
            # Image asset → apply template overlay (titles, subtitles)
            composed = rctx.work_dir / f"segment_{ctx.index:03d}_composed.png"
            self._compose_image_template(ctx.visual_input, seg, composed, rctx)
            ctx.visual_input = composed
            
        elif ctx.render_mode in ("user_video", "reference_clip"):
            # Video asset → need to extract clip first, then overlay subtitles
            # (handled in _step_assemble for video modes)
            pass
    
    def _step_assemble(self, ctx: SegmentContext, rctx) -> None:
        """Create the final MP4 segment from visual + audio."""
        out_path = rctx.work_dir / f"segment_{ctx.index:03d}.mp4"
        tts_path = ctx.tts_path
        
        if ctx.render_mode in ("prompt_card", "image"):
            # Image-based: FFmpeg -loop 1 + audio
            self._assemble_from_image(ctx.visual_input, tts_path, out_path,
                                      ctx.duration, rctx)
        elif ctx.render_mode in ("user_video", "reference_clip"):
            # Video-based: trim + overlay + audio
            self._assemble_from_video(ctx.visual_input, tts_path, out_path,
                                      ctx, rctx)
        
        ctx.video_segment_path = out_path
    
    # ── Helper: assemble from image (Pixelle-Video create_video_from_image pattern) ──
    
    def _assemble_from_image(self, image_path, audio_path, output, duration, rctx):
        """Create video from image + audio in ONE ffmpeg call."""
        from services.compositor import _cinematic_motion, _apply_visual_fx, _ass_for_segment
        
        seg = rctx.segments[0]  # ... 需要传递 segment 引用
        vf = _cinematic_motion(seg.type, rctx.width, rctx.height, duration,
                               camera=getattr(seg, 'camera', '静态'))
        
        inputs = ["-loop", "1", "-i", str(image_path)]
        if audio_path and Path(audio_path).exists():
            inputs.extend(["-i", str(audio_path)])
            cmd = [
                rctx.settings.ffmpeg_path, "-y",
                *inputs,
                "-t", f"{duration:.3f}",
                "-vf", vf,
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-shortest",
                str(output),
            ]
        else:
            cmd = [
                rctx.settings.ffmpeg_path, "-y",
                *inputs,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", f"{duration:.3f}",
                "-vf", vf,
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-shortest",
                str(output),
            ]
        _run(cmd)
    
    # ── Helpers ──
    
    def _render_prompt_card(self, segment, output_path, rctx):
        """Render AI prompt card to PNG — try HTML first, fallback to Pillow."""
        from services.ai_video_service import AIVideoService, PromptCard
        
        prod_name = (rctx.script.metadata or {}).get("productName", "") or ""
        prod_type = (rctx.script.metadata or {}).get("productType", "其他") or "其他"
        
        ai_result = AIVideoService(self.settings, platform="seedance").generate(
            segment, product_name=prod_name, product_type=prod_type)
        
        if isinstance(ai_result, PromptCard):
            # Try HTML template (Pixelle-Video pattern)
            html_ok = self._render_html_card(ai_result, segment, output_path)
            if not html_ok:
                # Fallback to Pillow blueprint
                from services.blueprint_renderer import render_blueprint_card
                render_blueprint_card(output_path, segment_type=segment.type,
                    visual_prompt=ai_result.prompt_text[:300],
                    script_text=ai_result.subtitle_text or "",
                    duration=ai_result.duration,
                    camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                    pace=ai_result.pace, emotion=ai_result.emotion)
    
    def _render_html_card(self, ai_result, segment, output_path) -> bool:
        """Use Playwright HTML template to render prompt card."""
        try:
            from services.frame_renderer import _render_prompt_card_html
            html_path = _render_prompt_card_html(
                prompt_text=ai_result.prompt_text[:500],
                subtitle_text=ai_result.subtitle_text or "",
                camera=ai_result.camera, visual_fx=ai_result.visual_fx,
                duration=ai_result.duration, emotion=ai_result.emotion,
                cost=ai_result.estimated_cost_usd,
            )
            if html_path:
                import shutil
                shutil.copy2(html_path, output_path)
                return True
        except Exception:
            pass
        return False
    
    def _compose_image_template(self, image_path, segment, output, rctx):
        """Apply HTML template overlay to a user-uploaded image."""
        # TODO: Use HTMLFrameGenerator-like approach from Pixelle-Video
        # For now, just copy the image as-is
        import shutil
        shutil.copy2(image_path, output)
    
    def _assemble_from_video(self, video_path, tts_path, output, ctx, rctx):
        """Trim video clip + overlay subtitles + replace audio."""
        from services.compositor import build_video_command
        
        seg = ctx.segment
        is_reference = (ctx.render_mode == "reference_clip")
        
        cmd = build_video_command(
            ffmpeg_path=rctx.settings.ffmpeg_path,
            input_path=video_path,
            output_path=output,
            ass_path=self._make_ass(seg, rctx),
            duration=ctx.duration,
            width=rctx.width, height=rctx.height,
            version=rctx.version, segment_type=seg.type,
            has_audio=(not is_reference and not tts_path),
        )
        _run(cmd)
        
        # Merge TTS audio if available
        if tts_path and Path(tts_path).exists():
            from services.compositor import _merge_video_audio_smart
            mixed = output.with_name(f"{output.stem}_mixed.mp4")
            _merge_video_audio_smart(str(output), str(tts_path), str(mixed),
                                     ffmpeg_path=rctx.settings.ffmpeg_path)
            if mixed.exists() and mixed.stat().st_size > 0:
                mixed.replace(output)
    
    def _make_ass(self, segment, rctx) -> Path:
        """Create ASS subtitle file for this segment."""
        from services.compositor import _ass_for_segment, _output_duration
        ass_path = rctx.work_dir / f"segment_{ctx.index:03d}.ass"
        out_dur = _output_duration(segment.duration, rctx.version, segment.type)
        ass_path.write_text(_ass_for_segment(segment, rctx.version, out_dur), encoding="utf-8")
        return ass_path
```

### Phase 3: HTML 模板系统升级

**新建 `ai-services/templates/segment_default.html`**:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="template:media-width" content="1080">
<meta name="template:media-height" content="1920">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: 1080px; height: 1920px;
    overflow: hidden;
    font-family: 'PingFang SC', 'Noto Sans SC', sans-serif;
  }
  .bg { position: absolute; inset: 0; }
  .bg img, .bg video { width: 100%; height: 100%; object-fit: cover; }
  .overlay { position: absolute; inset: 0; }
  .segment-badge {
    position: absolute; top: 60px; left: 60px;
    padding: 16px 32px;
    font-size: 36px; font-weight: 700; letter-spacing: 4px;
    border-radius: 8px;
    /* Color driven by segment_type via CSS class */
  }
  .type-hook { background: #FF6B35; color: #fff; }
  .type-pain { background: #8B5CF6; color: #fff; }
  .type-product { background: #3B82F6; color: #fff; }
  .type-proof { background: #10B981; color: #fff; }
  .type-cta { background: #F59E0B; color: #fff; }
  .subtitle-area {
    position: absolute; bottom: 280px; left: 80px; right: 80px;
  }
  .subtitle-text {
    font-size: 52px; font-weight: 600; color: #fff;
    text-shadow: 0 2px 12px rgba(0,0,0,0.8);
    line-height: 1.6;
    text-align: center;
  }
  .prompt-info {
    position: absolute; bottom: 100px; left: 80px; right: 80px;
    display: flex; gap: 24px; justify-content: center;
  }
  .prompt-tag {
    padding: 8px 20px; font-size: 24px;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px; color: rgba(255,255,255,0.9);
  }
</style>
</head>
<body>
  <div class="bg">
    {{#image}}<img src="{{image}}">{{/image}}
    {{^image}}<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); width:100%; height:100%"></div>{{/image}}
  </div>
  <div class="overlay">
    <div class="segment-badge type-{{segment_type}}">{{segment_type_zh}}</div>
    <div class="subtitle-area">
      <div class="subtitle-text">{{text}}</div>
    </div>
    {{#show_prompt_info}}
    <div class="prompt-info">
      <span class="prompt-tag">🎥 {{camera}}</span>
      <span class="prompt-tag">✨ {{visual_fx}}</span>
      <span class="prompt-tag">⏱ {{duration}}s</span>
    </div>
    {{/show_prompt_info}}
  </div>
</body>
</html>
```

### Phase 4: 删除 compositor.py 的 if/else 分支

简化后的 `compositor.py` 只保留 FFmpeg 命令构建函数:

```python
# 保留 (无改动):
# - build_image_command()
# - build_video_command()
# - build_placeholder_command()
# - _cinematic_motion()
# - _apply_visual_fx()
# - _version_filters()
# - _ass_for_segment()
# - _strip_production_params()
# - _merge_video_audio_smart()
# - _probe_duration()
# - _has_audio_stream()
# - _run()

# 删除 (迁移到 SegmentProcessor):
# - render() 方法中的 400+ 行 if/else
# - render() 方法中的 TTS 事后合成逻辑
# - 重复的 AI prompt card 渲染逻辑
```

---

## 9. 验收标准

### Phase 1 验收 (TTS 驱动时长)

- [ ] TTS 在视频段创建**之前**完成合成
- [ ] 每个分镜的 `segment.duration` 由 TTS 音频实际时长决定
- [ ] `-t {frame.duration}` 参数使用音频时长
- [ ] 音画同步 100% (无冻结帧、无静音尾)

### Phase 2 验收 (SegmentProcessor)

- [ ] 四类 render_mode (user_video / image / prompt_card / reference_clip) 均能正确渲染
- [ ] 每段通过统一的 `process()` 方法处理
- [ ] compositor.py 行数从 600+ 降至 300-
- [ ] 无回归: 所有原有分镜类型(hook/pain/product/proof/cta)都能正确渲染

### Phase 3 验收 (HTML 模板)

- [ ] 所有 prompt_card 段使用 HTML 模板渲染
- [ ] 用户上传图片可选择叠加 HTML 模板
- [ ] 模板变量 (segment_type, script, camera, visual_fx) 正确替换
- [ ] Playwright 渲染 PNG 清晰度 ≥ 1080×1920

### Phase 4 验收 (整体)

- [ ] `pytest ai-services/tests/` 全部通过
- [ ] `npm run build` TypeScript 零错误
- [ ] 端到端测试: 上传视频 → 分析 → 生成脚本 → 审核 → 渲染 → 播放
- [ ] 零 API Key 用户路径: 审核页 → 复制提示词 → 手动生成 → 回传 → 渲染

---

## 附录: 改造时间估算

| Phase | 内容 | 工时 | 风险 |
|------|------|:---:|------|
| Phase 1 | TTS 驱动时长 | 3h | 低 — 纯顺序调整 |
| Phase 2 | SegmentProcessor | 5h | 中 — 需要彻底理解原有 if/else 逻辑 |
| Phase 3 | HTML 模板升级 | 3h | 低 — 已有 frame_renderer.py 基础 |
| Phase 4 | 清理+合并 | 2h | 低 — 删除重复代码 |
| 测试 | 端到端 + 回归 | 3h | 中 — 需要覆盖所有素材组合 |
| **总计** | | **16h** | |

> **结论**: 完全可以改，而且应该改。Pixelle-Video 的视频生成逻辑已经被验证为可工作的架构，StructForge 需要的不是照搬代码，而是**嫁接其架构思想** — TTS 驱动时长 + SegmentProcessor 统一入口 + HTML 模板统一渲染。这三个改造将从根本上解决当前 compositor.py 的复杂性和音画同步问题。
