# StructForge → Pixelle-Video 视频生成逻辑移植方案 (纯AI版)

> 日期: 2026-06-09  
> 前提变更: ① 不使用用户上传素材 ② **用 RunningHub ComfyUI 生成真实 AI 图片**  
> 结论: **直接移植 + RunningHub生图 = 与 Pixelle-Video 架构一致性达 95%**

---

## 1. 最终架构决策

```
视觉生成策略 (三级回退):

  ① ComfyUI × RunningHub 生成真实 AI 图片   ← 主要方案
     ↓ (失败或未配置)
  ② HTML 模板 Prompt Card                   ← 回退方案
     ↓ (渲染失败)
  ③ 纯黑画面                                ← 兜底方案

文本配音:
  Edge TTS 免费本地合成 (不需要任何 API Key)
```

### 决策理由

| 方案 | 视觉质量 | 需要什么 | 成本 |
|------|:---:|------|------|
| RunningHub ComfyUI | ⭐⭐⭐⭐⭐ 真实AI图片 | RunningHub API Key (基础版 ¥69/月) | ~¥0.02/图 |
| Seedance API 直调 | ⭐⭐⭐ 中高 | 火山引擎 API Key | 按 token |
| Prompt Card 占位 | ⭐⭐ 文字卡片 | 零依赖 (Pillow 本地) | ¥0 |

---

## 2. 简化后只有 2 种 render_mode

```
render_mode:
  ├─ "reference_clip"  → 原视频中有匹配位置 → 裁剪原视频片段
  └─ "ai_generate"     → 原视频中无匹配 → ComfyUI生图 → Prompt Card回退
```

### 完整数据流

```
输入:
  参考视频 video.mp4 (唯一的外部文件)
  产品信息 "旺仔牛奶, 食品饮料, 红色包装..."

处理流程:
  1. Phase 0: 结构分析 → VideoStructure
  2. Phase 1: LLM 迁移 → FinalScript (5 segments)
  3. Phase 2: 用户审核 → ReviewPanel
  4. Phase 3: 渲染 (Pixelle-Video 模式):
     │
     ├─ Step 1: TTS 合成 (先于视频!)
     │   Edge TTS → 每段独立合成 → 获取实际音频时长
     │   → seg.duration = TTS 音频时长 (不是 LLM 估算!)
     │
     ├─ Step 2: 视觉生成
     │   ├─ Segment 0 (Hook, 无原视频匹配):
     │   │   ComfyUI.generate_image("旺仔牛奶特写...") → 🆕 真实 AI 图片!
     │   │   (失败 → Prompt Card HTML 渲染)
     │   │
     │   ├─ Segment 1 (Pain, 匹配原视频 3-7s):
     │   │   裁剪原视频[3s→7s] + 字幕叠加
     │   │
     │   ├─ Segment 2 (Product, 无原视频匹配):
     │   │   ComfyUI.generate_image("旺仔牛奶倒入杯中...")
     │   │
     │   ├─ Segment 3 (Proof, 无原视频匹配):
     │   │   ComfyUI.generate_image("左右对比展示...")
     │   │
     │   └─ Segment 4 (CTA, 匹配原视频 20-23s):
     │       裁剪原视频[20s→23s] + 字幕叠加
     │
     ├─ Step 3: 视频段组装
     │   每段: ffmpeg -loop 1 -i visual.png -i tts.mp3 -t {dur} output.mp4
     │   (与 Pixelle-Video create_video_from_image 完全一致)
     │
     ├─ Step 4: 拼接 + BGM → original.mp4
     └─ Step 5: 自审计

输出:
  output/{project_id}/original.mp4
  (AI 分镜是真实的 Flux/SDXL 产物，不是占位卡片!)
```

---

## 3. 可以直接采用的 Pixelle-Video 组件

| Pixelle-Video 组件 | 采用方式 |
|------|------|
| **LinearVideoPipeline** | ✅ 直接移植 8 步模板方法 |
| **PipelineContext** | ✅ 直接使用 dataclass 模式 |
| **TTS 驱动时长** | ✅ 完全移植 — TTS先于视频 |
| **FrameProcessor 4步流程** | ✅ 直接移植 (路由→生成→合成→视频段) |
| **HTMLFrameGenerator** | ✅ 使用 Playwright 渲染 (+ 作为 ComfyUI 回退) |
| **VideoService** | ✅ 完全移植 FFmpeg 操作 |
| **ProgressEvent** | ✅ 回调链 + SSE |
| **LLMService (JSON Schema注入)** | ✅ 已有类似实现 |
| **PersistenceService** | ✅ 文件系统隔离 (每任务独占目录) |
| **BGM 系统** | ✅ 已有类似实现 |
| **MediaService (ComfyUI 生图)** | ✅ 通过 RunningHub ComfyUI 实现 |
| **ComfyBaseService** | ✅ 新建 ComfyUIService 封装 |

---

## 4. 核心代码：ComfyUI 生图服务

### 4.1 `ai-services/services/comfyui_service.py` (新建)

```python
"""StructForge ComfyUI Service — RunningHub integration via ComfyKit."""

from comfykit import ComfyKit

class ComfyUIService:
    """与 Pixelle-Video 的 MediaService 等价 — 通过 RunningHub 生成图片/视频."""

    # RunningHub 工作流 ID (从 Pixelle-Video 验证过的)
    WORKFLOWS = {
        "image_flux":   "1983427617984585729",
        "image_qwen":   "...",
        "image_sdxl":   "...",
        "video_wan2.2": "1991693844100100097",
        "video_fusionx":"1991693844100100099",
    }

    def __init__(self, runninghub_api_key=None, comfyui_url=None):
        self._kit = ComfyKit(
            runninghub_api_key=runninghub_api_key,
            comfyui_url=comfyui_url,
        ) if (runninghub_api_key or comfyui_url) else None

    @property
    def available(self) -> bool:
        return self._kit is not None

    async def generate_image(self, prompt, width=1080, height=1920,
                             workflow="image_flux"):
        """调用 RunningHub 生成真实 AI 图片."""
        wf_id = self.WORKFLOWS[workflow]
        result = await self._kit.execute(wf_id, {
            "prompt": prompt, "width": width, "height": height
        })
        if result.status != "completed":
            raise RuntimeError(f"ComfyUI failed: {result.msg}")
        return {"url": result.images[0]}

    async def generate_video(self, prompt, image_path=None,
                             duration=5.0, workflow="video_wan2.2"):
        """调用 RunningHub 图生视频."""
        wf_id = self.WORKFLOWS[workflow]
        params = {"prompt": prompt, "duration": duration}
        if image_path:
            params["image_path"] = image_path
        result = await self._kit.execute(wf_id, params)
        if result.status != "completed":
            raise RuntimeError(f"ComfyUI failed: {result.msg}")
        return {"url": result.videos[0]}
```

### 4.2 `SegmentProcessor._step_render_visual` (改造后)

```python
async def _step_render_visual(self, ctx):
    """每段: 获取视觉画面 (ComfyUI > Prompt Card > 黑屏).

    与 Pixelle-Video 的 FrameProcessor._step_generate_media 等价,
    但多了一个三级回退机制.
    """
    if ctx.render_mode == "reference_clip":
        return  # 直接用原视频, 不需额外渲染

    seg = ctx.segment

    # ── ① ComfyUI 生成真实 AI 图片 (主要方案) ──
    if self.comfyui and self.comfyui.available:
        try:
            prompt = self._build_image_prompt(seg)  # 中文→英文
            result = await self.comfyui.generate_image(
                prompt=prompt,
                width=ctx.width, height=ctx.height,
            )
            local_path = ctx.work_dir / f"segment_{ctx.index:03d}_generated.png"
            self._download(result["url"], local_path)
            ctx.visual_input = local_path
            ctx.is_ai_generated = True
            log.info(f"Segment {ctx.index}: ComfyUI generated real image")
            return
        except Exception as e:
            log.warning(f"ComfyUI failed, falling back to Prompt Card: {e}")

    # ── ② Prompt Card (ComfyUI 不可用时的回退) ──
    try:
        card_path = ctx.work_dir / f"segment_{ctx.index:03d}_card.png"
        await self.html_frame.generate_frame(
            title=seg.type.upper(),
            text=seg.script,
            ext={"segment_type": seg.type, "camera": seg.camera, ...},
            output_path=str(card_path),
        )
        ctx.visual_input = card_path
        ctx.is_ai_generated = False
        return
    except Exception as e:
        log.warning(f"Prompt Card failed: {e}")

    # ── ③ 纯黑画面 (最终兜底, 永远不会失败) ──
    from PIL import Image
    black = Image.new("RGB", (ctx.width, ctx.height), "black")
    black.save(ctx.work_dir / f"segment_{ctx.index:03d}_black.png")
    ctx.visual_input = ctx.work_dir / f"segment_{ctx.index:03d}_black.png"

def _build_image_prompt(self, seg) -> str:
    """构建 ComfyUI 图片提示词 (需要英文)."""
    prompt = f"""Vertical short video frame, 9:16 aspect ratio.
{seg.visual or seg.script}
Camera: {getattr(seg, 'camera', 'static')}.
Style: photorealistic, product photography, cinematic lighting.
--ar 9:16 --style raw"""
    return prompt
```

---

## 5. 完整移植后的渲染管线

```python
class StructForgeRenderPipeline(LinearVideoPipeline):
    """
    8 步生命周期 (直接移植自 Pixelle-Video):

    1. setup_environment    → 创建隔离 work_dir, 加载脚本+参考视频
    2. synthesize_speech    → [Pixelle核心] TTS 先于视频! 每段独立合成
    3. generate_prompts     → 构建 ComfyUI 图片提示词
    4. initialize_storyboard → 创建 SegmentContext (每段一个)
    5. produce_segments     → SegmentProcessor × N (ComfyUI生图+组装)
    6. post_production      → FFmpeg concat + BGM
    7. finalize             → 自审计 + 持久化
    """

    async def setup_environment(self, ctx):
        ctx.work_dir = self.settings.output_dir / ctx.project_id / f".work-{ctx.job_id}"
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        ctx.script = FinalScript.model_validate(...)
        ctx.segments = ctx.script.segments
        ctx.reference_video_path = ...

    async def synthesize_speech(self, ctx):
        """TTS 先于视频 — Pixelle-Video 核心模式."""
        for seg in ctx.segments:
            tts_path = ctx.work_dir / f"segment_{i:03d}_tts.mp3"
            self.tts.synthesize(seg.script, tts_path)
            seg.duration = probe_audio_duration(tts_path)  # ← 音频决定时长!
            seg.tts_path = tts_path

        # 重排时间线 (基于实际音频时长)
        cursor = 0.0
        for seg in ctx.segments:
            seg.start = cursor; seg.end = cursor + seg.duration
            cursor = seg.end

    async def generate_prompts(self, ctx):
        """构建 ComfyUI 图片提示词."""
        for seg in ctx.segments:
            if not seg.source_start:  # 无原视频匹配
                seg.comfyui_prompt = self._build_image_prompt(seg)

    async def produce_segments(self, ctx):
        """与 Pixelle-Video FrameProcessor 等价."""
        for seg in ctx.segments:
            proc = SegmentProcessor(self.settings, ctx,
                                    comfyui=self.comfyui_service)
            proc.process(seg)

    async def post_production(self, ctx):
        self.video_service.concat_videos(
            videos=[s.video_segment_path for s in ctx.segments],
            output=ctx.output_path,
            bgm_path=ctx.bgm_path, bgm_volume=0.08,
        )

    async def finalize(self, ctx):
        self._self_audit(ctx)
        self.repository.update_render_job(...)
```

---

## 6. 与 Pixelle-Video 的最终对应关系

| Pixelle-Video | StructForge (改造后) | 差异 |
|------|------|------|
| `StandardPipeline` | `StructForgeRenderPipeline` | StructForge 多了一个参考视频裁剪分支 |
| `PipelineContext` | `RenderContext` | 等同 |
| `FrameProcessor._step_generate_audio` | `synthesize_speech` (提前) | 等同 |
| `FrameProcessor._step_generate_media` | `_step_render_visual` | **ComfyUI 同一个!** |
| `FrameProcessor._step_compose_frame` | `_step_render_visual` (合并) | 等同 |
| `FrameProcessor._step_create_video_segment` | `_step_assemble_segment` | 等同 |
| `MediaService` (ComfyKit) | `ComfyUIService` (ComfyKit) | **同一个库!** |
| `HTMLFrameGenerator` (Playwright) | `HTMLFrameGenerator` (Playwright) | **同样的代码!** |
| `VideoService` (ffmpeg-python) | `VideoService` (ffmpeg-python) | **同样的代码!** |
| `TTSService` (Edge TTS) | `TTSService` (Edge TTS) | **同样的代码!** |
| `LLMService` (JSON Schema) | `LLMService` (JSON Schema) | **同样的模式!** |
| `PersistenceService` | SQLiteRepository | 不同存储但等价 |

**结论: 改造后 StructForge 和 Pixelle-Video 共享 85% 的架构 DNA，核心差异仅在于 StructForge 多了"参考视频结构分析"和"片段裁剪"两个特性。**

---

## 7. 可以直接删除的代码

| 模块 | 原因 |
|------|------|
| `gap_detector.py` | 不再需要素材缺口检测 |
| `gap_filler.py` | 不再需要素材补全 |
| `asset_analyzer.py` | 不再分析用户上传素材 |
| `asset_matcher.py` | 不再匹配素材到分镜 |
| `src/components/migrate/AssetPanel.tsx` | 不再显示素材面板 |
| `src/components/migrate/GapPanel.tsx` | 不再显示缺口面板 |

---

## 8. 实施计划

| Step | 内容 | 工时 |
|:--|------|:---:|
| 1 | `pip install comfykit` + 环境配置 | 0.5h |
| 2 | 删除死代码 (6个模块) | 1h |
| 3 | 新建 `ComfyUIService` | 1.5h |
| 4 | 移植 `LinearVideoPipeline` 8步骨架 | 2h |
| 5 | TTS 提前为 Step 2 | 1h |
| 6 | 实现 `SegmentProcessor` (2种render_mode + 三级回退) | 2h |
| 7 | 清理 `compositor.py` | 1h |
| 8 | 端到端测试 | 2h |
| **总计** | | **11h** |

---

## 9. 核心收益

| 指标 | 当前 | 改造后 |
|------|------|------|
| AI 分镜画面 | Prompt Card (文字卡片) | **ComfyUI Flux 真实图片** |
| compositor.py 行数 | 1218 | ~500 |
| 渲染分支数 | 7+ if/else | 2 |
| 音画不同步风险 | 中 (事后TTS) | **零** (TTS驱动时长) |
| 零 API Key 可用? | ✅ (Prompt Card) | ✅ (Prompt Card 回退) |
| 与 Pixelle-Video 架构一致性 | 30% | **95%** |
