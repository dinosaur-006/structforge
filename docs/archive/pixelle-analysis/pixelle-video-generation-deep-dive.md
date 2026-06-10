# Pixelle-Video 视频生成逻辑深度分析报告

> 日期: 2026-06-09  
> 源码版本: Pixelle-Video-main (Apache 2.0)  
> 分析范围: 完整视频生成管线 — 从输入文本到最终 MP4

---

## 目录

1. [架构总览](#1-架构总览)
2. [管道系统 (Pipeline System)](#2-管道系统)
3. [完整视频生成流程](#3-完整视频生成流程)
4. [FrameProcessor: 每帧处理核心](#4-frameprocessor-每帧处理核心)
5. [TTS 驱动的时长架构](#5-tts-驱动的时长架构)
6. [媒体生成系统](#6-媒体生成系统)
7. [视频合成层 (VideoService)](#7-视频合成层)
8. [HTML 模板帧渲染](#8-html-模板帧渲染)
9. [LLM 服务与结构化输出](#9-llm-服务与结构化输出)
10. [提示词工程体系](#10-提示词工程体系)
11. [数据模型](#11-数据模型)
12. [API 层](#12-api-层)
13. [与 StructForge 对比分析](#13-与-structforge-对比分析)
14. [关键设计模式与启示](#14-关键设计模式与启示)

---

## 1. 架构总览

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────┐
│                    API 层 (FastAPI)                    │
│  /api/video/generate/sync  |  /api/video/generate/async │
├──────────────────────────────────────────────────────┤
│               PixelleVideoCore (服务层)                │
│  ┌──────┐ ┌──────┐ ┌───────┐ ┌───────┐ ┌─────────┐ │
│  │ LLM  │ │ TTS  │ │ Media │ │ Video │ │ Persist │ │
│  │Service│ │Service│ │Service│ │Service│ │ Service │ │
│  └──────┘ └──────┘ └───────┘ └───────┘ └─────────┘ │
│              ┌──────────────────────┐                │
│              │   FrameProcessor     │                │
│              │  (TTS→Media→Compose  │                │
│              │   →Video Segment)    │                │
│              └──────────────────────┘                │
├──────────────────────────────────────────────────────┤
│               管道层 (Pipelines)                       │
│  BasePipeline → LinearVideoPipeline                  │
│    ├── StandardPipeline (默认)                        │
│    ├── AssetBasedPipeline (用户素材)                   │
│    └── CustomPipeline (自定义模板)                     │
├──────────────────────────────────────────────────────┤
│            基础设施层 (Infrastructure)                  │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ ComfyKit │ │ Playwright│ │ FFmpeg (ffmpeg-py) │   │
│  │(图片/视频)│ │(HTML渲染) │ │ (视频编解码/合成)   │   │
│  └──────────┘ └──────────┘ └────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 实现方式 |
|------|---------|
| **管道即策略** | 每个 Pipeline 是独立的视频生成策略，可插拔注册 |
| **模板方法模式** | LinearVideoPipeline 定义 8 步生命周期，子类覆写特定步骤 |
| **TTS 驱动时长** | 每帧时长 = TTS 音频时长，杜绝音画不同步 |
| **HTML 模板渲染** | 所有帧画面通过 Playwright 渲染 HTML 模板生成 |
| **懒加载 + 热重载** | ComfyKit 实例按需创建，配置变更自动重建 |
| **文件系统隔离** | 每次任务独占 `output/{task_id}/` 目录 |

---

## 2. 管道系统

### 2.1 继承层级

```
BasePipeline (ABC)                  ← 定义 __call__ 接口 + 进度上报
    │
    ├── LinearVideoPipeline         ← 模板方法模式 (8步生命周期)
    │       │
    │       ├── StandardPipeline    ← "主题→旁白→图片→视频" 通用流程
    │       ├── AssetBasedPipeline  ← "用户素材→LLM分配→场景视频"
    │       └── CustomPipeline      ← 自定义流程模板
    │
    └── [用户自定义 Pipeline]        ← 直接继承 BasePipeline
```

### 2.2 BasePipeline — 最小接口

```python
class BasePipeline(ABC):
    def __init__(self, pixelle_video_core):
        self.core = pixelle_video_core      # 统一服务访问入口
        self.llm  = pixelle_video_core.llm  # 快捷访问
        self.tts  = pixelle_video_core.tts
        self.media = pixelle_video_core.media
        self.video = pixelle_video_core.video

    @abstractmethod
    async def __call__(self, text, progress_callback=None, **kwargs) -> VideoGenerationResult:
        pass

    def _report_progress(self, callback, event_type, progress, **kwargs):
        # 统一的进度上报 → ProgressEvent
```

**关键设计**: 管道通过 `self.core` 获取所有服务，不直接依赖具体实现。新管道只需实现 `__call__`。

### 2.3 LinearVideoPipeline — 模板方法模式

这是 Pixelle-Video 最核心的设计模式。定义了 **8 步生命周期**:

```
__call__ (模板方法，不可覆写)
  │
  ├─ Phase 1: 准备
  │   └─ setup_environment()          # 创建 task_dir, task_id
  │
  ├─ Phase 2: 内容创作
  │   ├─ generate_content()           # 主题→旁白 (LLM)
  │   └─ determine_title()            # 生成标题 (LLM)
  │
  ├─ Phase 3: 视觉规划
  │   ├─ plan_visuals()               # 旁白→图片提示词 (LLM)
  │   └─ initialize_storyboard()      # 创建 Storyboard + Frame
  │
  ├─ Phase 4: 资产生成
  │   └─ produce_assets()             # 每帧: TTS→图片→合成→视频段
  │
  ├─ Phase 5: 后期制作
  │   └─ post_production()            # 拼接视频段 + BGM
  │
  └─ Phase 6: 最终化
      └─ finalize()                   # 创建结果对象 + 持久化元数据
```

**PipelineContext** 是步骤间传递状态的载体:

```python
@dataclass
class PipelineContext:
    # 输入
    input_text: str
    params: Dict[str, Any]
    progress_callback: Optional[Callable]

    # 任务状态
    task_id: Optional[str]
    task_dir: Optional[str]

    # 内容
    title: Optional[str]
    narrations: List[str]

    # 视觉
    image_prompts: List[Optional[str]]

    # 配置与分镜
    config: Optional[StoryboardConfig]
    storyboard: Optional[Storyboard]

    # 输出
    final_video_path: Optional[str]
    result: Optional[VideoGenerationResult]
```

### 2.4 StandardPipeline — 默认通用流程

```
输入: "如何提高学习效率" (主题)
  │
  ├─ setup_environment      → 创建 output/20250609_143022_abc123/
  ├─ generate_content       → LLM 生成 5 段旁白
  ├─ determine_title        → LLM 生成标题 "高效学习法则"
  ├─ plan_visuals           → LLM 生成 5 段图片提示词 (英文)
  ├─ initialize_storyboard  → StoryboardConfig + 5 个 StoryboardFrame
  ├─ produce_assets         → 对每帧调用 FrameProcessor
  │   ├─ Frame 1: TTS → ComfyUI 生图 → HTML 合成 → Image→Video
  │   ├─ Frame 2: TTS → ComfyUI 生图 → HTML 合成 → Image→Video
  │   └─ ...
  ├─ post_production        → FFmpeg concat + BGM 混音
  └─ finalize               → VideoGenerationResult + 持久化
```

**支持两种模式**:
- `mode="generate"`: LLM 从主题生成旁白 (默认)
- `mode="fixed"`: 直接按段落/行/句分割输入文本

**模板智能检测**:
```python
template_type = get_template_type(template_name)
# "image"  → 需要 ComfyUI 生图
# "video"  → 需要 ComfyUI 生视频
# "static" → 跳过所有媒体生成 (纯文字视频，更快更便宜)
```

### 2.5 AssetBasedPipeline — 用户素材驱动

这是一个**完全不同的工作流**，专为有素材库的用户设计:

```
输入: [image1.jpg, image2.jpg, video1.mp4] + "宠物店年终促销"
  │
  ├─ setup_environment      → 分析每个素材:
  │   ├─ image1.jpg → ComfyUI ImageAnalysis → "一只金毛犬在草地奔跑"
  │   ├─ image2.jpg → ComfyUI ImageAnalysis → "猫爬架特写"
  │   └─ video1.mp4 → ComfyUI VideoAnalysis → "宠物店内景巡游"
  │
  ├─ generate_content       → LLM 结构化输出 (VideoScript):
  │   ┌─────────────────────────────────────────────────┐
  │   │ Scene 1: asset=image1.jpg, narr=["欢迎来到..."], dur=8s  │
  │   │ Scene 2: asset=video1.mp4, narr=["我们提供..."], dur=10s │
  │   └─────────────────────────────────────────────────┘
  │
  ├─ plan_visuals           → 转换格式 (LLM 已分配，此步仅做兼容)
  ├─ initialize_storyboard  → 每个 scene → StoryboardFrame
  │   (image→frame.image_path, video→frame.video_path)
  │
  ├─ produce_assets         → 对每个 scene:
  │   ├─ TTS 旁白 (支持多句合并)
  │   ├─ 可选: API Video 动画 (image→video 转换)
  │   └─ FrameProcessor 合成
  │
  └─ post_production → finalize
```

**关键差异**:
- 不需要 ComfyUI 生图 (素材由用户提供)
- LLM 用 **Structured Output** (Pydantic `VideoScript`) 直接分配素材
- 支持多句旁白合并 (每场景 1-3 句 → FFmpeg concat 音频)
- 支持素材的 API 动画化 (静态图片 → AI 视频)

---

## 3. 完整视频生成流程

### 3.1 请求入口

```
POST /api/video/generate/sync
{
  "text": "如何提高学习效率",
  "mode": "generate",
  "n_scenes": 5,
  "frame_template": "1080x1920/image_default.html",
  "tts_workflow": "runninghub/tts_edge.json",
  "media_workflow": "image_flux.json",
  "bgm_path": "upbeat.mp3",
  "bgm_volume": 0.3
}
```

### 3.2 调用链

```
FastAPI router
  → pixelle_video.generate_video(text=..., pipeline="standard", **params)
    → StandardPipeline.__call__(text, **params)
      → [8步生命周期]
        → FrameProcessor.__call__() × N帧
          → [4步子流程: Audio → Media → Compose → Segment]
      → VideoGenerationResult
```

### 3.3 进度上报机制

```python
# 管道层
self._report_progress(callback, "generating_narrations", 0.05)

# 帧处理层
progress_callback(ProgressEvent(
    event_type="frame_step",
    progress=0.45,
    frame_current=3,
    frame_total=5,
    step=2,            # 1=audio, 2=media, 3=compose, 4=video
    action="media"
))
```

进度范围划分:
| 阶段 | 进度范围 |
|------|---------|
| 环境准备 | 0% - 1% |
| 标题生成 | 1% - 5% |
| 旁白生成 | 5% - 15% |
| 图片提示词 | 15% - 20% |
| 帧处理 (每帧) | 20% - 80% |
| 拼接 | 80% - 95% |
| 最终化 | 95% - 100% |

### 3.4 RunningHub 并行处理

StandardPipeline 支持 RunningHub 工作流的并行帧处理:

```python
if is_runninghub and runninghub_concurrent_limit > 1:
    semaphore = asyncio.Semaphore(runninghub_concurrent_limit)
    # 所有帧并发执行 (受信号量限制)
    tasks = [process_frame_with_semaphore(i, frame) for ...]
    results = await asyncio.gather(*tasks)
else:
    # 串行处理 (本地 ComfyUI)
    for frame in storyboard.frames:
        ...
```

---

## 4. FrameProcessor: 每帧处理核心

### 4.1 四步处理流程

```
FrameProcessor.__call__(frame, storyboard, config)
  │
  ├─ Step 1: _step_generate_audio()     [TTS]
  │   ├─ 调用 self.core.tts(text=frame.narration, ...)
  │   ├─ frame.audio_path = 音频路径
  │   └─ frame.duration = 音频时长 (ffprobe)
  │
  ├─ Step 2: _step_generate_media()     [Media Gen]
  │   ├─ 判断: image_prompt 不为 None → 需要生成
  │   ├─ 判断: image_path/video_path 已设置 → 跳过 (AssetBased)
  │   ├─ 调用 self.core.media(prompt=image_prompt, ...)
  │   ├─ 如果是视频工作流: media_params["duration"] = frame.duration
  │   ├─ 下载到本地: frame.image_path 或 frame.video_path
  │   └─ frame.media_type = "image" | "video"
  │
  ├─ Step 3: _step_compose_frame()      [HTML Compose]
  │   ├─ HTMLFrameGenerator(template_path)
  │   ├─ generator.generate_frame(
  │   │     title, text=frame.narration,
  │   │     image=media_path, ext={index}
  │   │   )
  │   └─ frame.composed_image_path = PNG 路径
  │
  └─ Step 4: _step_create_video_segment() [Video Segment]
      ├─ if media_type == "video":
      │   ├─ overlay_image_on_video()  ← HTML 叠加层覆到视频上
      │   └─ merge_audio_video(replace_audio=True)  ← 替换音频
      └─ if media_type == "image" or None:
          └─ create_video_from_image()  ← 静态图 + TTS 音频 → MP4
```

### 4.2 专家级处理决策表

| 条件 | 行为 |
|------|------|
| `image_prompt` 有值 + 无现有素材 | `_step_generate_media` → ComfyUI 生图 |
| `image_path` 已有值 | 跳过媒体生成，直接用现有图 (AssetBasedPipeline) |
| `video_path` 已有值 | 跳过媒体生成，直接用现有视频 |
| `image_prompt` 为 `None` (static模板) | 跳过媒体生成，frame.media_type=None |
| `media_type == "video"` | 视频+HTML叠加层+配音 |
| `media_type == "image"` 或 `None` | 静态图→视频+配音 |

### 4.3 API Video 首帧生成

当 `media_workflow` 为 `api/*` 时，FrameProcessor 支持自动首帧生成:

```python
async def _prepare_api_video_inputs(frame, config, api_video_params):
    # 1. 如果没有首帧图，自动用 ComfyUI 生成
    if not frame.image_path:
        first_frame_path = ...
        image_result = await self.core.media(
            prompt=frame.image_prompt,
            workflow=first_frame_workflow  # e.g., "image_flux.json"
        )
        frame.image_path = downloaded_path

    # 2. 如果支持 audio_driven_i2v，传入音频
    if "audio_driven_i2v" in adapter_abilities:
        api_video_params["audio_path"] = frame.audio_path
```

---

## 5. TTS 驱动的时长架构

这是 Pixelle-Video **最关键的架构决策**。

### 5.1 核心理念

> **音频决定视频长度，而非反过来。**

传统方案: 预设每帧 5 秒 → TTS → 音频拉伸/压缩 → 音画不同步  
Pixelle-Video: TTS → 获取音频时长 → 视频生成按此时长 → 完美同步

### 5.2 实现细节

```python
# FrameProcessor._step_generate_audio()
audio_path = await self.core.tts(text=frame.narration, ...)
frame.duration = self._get_audio_duration(audio_path)  # ffprobe

# FrameProcessor._step_generate_media()
if is_video_workflow and frame.duration:
    media_params["duration"] = frame.duration  # 传给 ComfyUI

# VideoService.create_video_from_image()
# 自动使用 t=audio_duration 强制视频时长=音频时长
ffmpeg.output(input_image, input_audio, output,
              t=audio_duration,  # ← 关键参数
              vcodec='libx264', acodec='aac')
```

### 5.3 时长容错机制

VideoService 内置智能时长调整 (merge_audio_video):

| 情况 | 策略 |
|------|------|
| 视频 < 音频 | 冻结最后一帧 (`tpad=stop_mode=clone`) 延展视频 |
| 视频 > 音频 (≤0.3s 容差) | 保持原样 |
| 视频 > 音频 (>0.3s 容差) | 裁剪视频 (`-t target_duration`) |
| 视频无音频轨道 | 直接添加音频 |
| 视频有音频 + replace=True | 替换原音频 |
| 视频有音频 + replace=False | `amix` 混合两路音频 |

### 5.4 TTS 双模式

```python
class TTSService:
    async def __call__(self, text, inference_mode="local", ...):
        if mode == "local":
            # Edge TTS (免费本地)
            return await self._call_local_tts(text, voice, speed, output_path)
        else:  # comfyui
            # ComfyUI 工作流 (RunningHub / 自建)
            return await self._call_comfyui_workflow(...)
```

- **Local 模式**: `edge_tts` 库 → 调用 Microsoft Edge TTS API，免费
- **ComfyUI 模式**: 通过 ComfyKit → RunningHub/自建 ComfyUI 执行 TTS 工作流
- 速度: `speed` 参数 → `speed_to_rate()` 转换为 Edge TTS rate 格式

---

## 6. 媒体生成系统

### 6.1 MediaService 架构

```
MediaService.__call__(prompt, workflow, media_type, ...)
  │
  ├─ workflow 以 "api/" 开头?
  │   └─ 委托给 APIProviderMediaService (直接调用 Seedance/Runway/Kling API)
  │
  └─ 本地工作流:
      ├─ _resolve_workflow(workflow) → {key, path, source}
      ├─ 构建 workflow_params
      ├─ kit.execute(workflow_input, workflow_params)
      │   ├─ RunningHub: workflow_input = "runninghub/xxx" → cloud execute
      │   └─ Selfhost:   workflow_input = "/path/to/workflow.json" → local execute
      └─ 返回 MediaResult(media_type="image"|"video", url, duration)
```

### 6.2 ComfyKit 懒加载与热重载

```python
class PixelleVideoCore:
    async def _get_or_create_comfykit(self):
        current_config = self._get_comfykit_config()  # {comfyui_url, api_key, ...}
        current_hash = md5(json.dumps(current_config))

        if self._comfykit is None or self._comfykit_config_hash != current_hash:
            # 配置变更 → 关闭旧实例 → 创建新实例
            if self._comfykit:
                await self._comfykit.close()
            self._comfykit = ComfyKit(**current_config)
            self._comfykit_config_hash = current_hash

        return self._comfykit
```

### 6.3 工作流自动发现

```python
def _scan_workflows(self):
    # 扫描 workflows/ 和 data/workflows/ 两层目录
    for source_name in list_resource_dirs("workflows"):
        for filename in list_resource_files("workflows", source_name):
            if (filename.startswith("image_") or filename.startswith("video_")):
                workflow_info = self._parse_workflow_file(file_path, source_name)
                workflows.append(workflow_info)
```

工作流命名约定:
- `image_*.json` → 图片生成工作流
- `video_*.json` → 视频生成工作流
- `runninghub/*.json` → RunningHub 云端工作流
- `api/*` → 直接调用 API (Seedance/Runway/Kling)

---

## 7. 视频合成层 (VideoService)

### 7.1 功能矩阵

| 方法 | 功能 | FFmpeg 实现 |
|------|------|------------|
| `concat_videos()` | 拼接多个视频段 | concat demuxer (快) / concat filter (兼容) |
| `merge_audio_video()` | 合并音频到视频 | 智能时长调整 + 冻结/裁剪 + 音频替换/混合 |
| `overlay_image_on_video()` | PNG 叠加到视频 | scale + overlay 滤镜 |
| `create_video_from_image()` | 静态图 → 视频 | loop=1 + t=audio_duration |
| `add_bgm()` | 背景音乐 | amix + stream_loop + volume |
| `_pad_video_to_duration()` | 延展视频 | tpad=clone (冻结) / black padding |
| `_trim_video_to_duration()` | 裁剪视频 | stream copy 快速裁剪 |

### 7.2 拼接策略选择

```python
if method == "demuxer":
    # concat demuxer: 无重编码，极快，要求相同编码格式
    ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4
else:
    # concat filter: 重编码，处理不同格式
    ffmpeg -i v1.mp4 -i v2.mp4 \
           -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
           -map "[v]" -map "[a]" output.mp4
```

### 7.3 BGM 系统

```python
def add_bgm(video, bgm, output, bgm_volume=0.3, loop=True, fade_in=0.0):
    bgm_input = ffmpeg.input(bgm, stream_loop=-1 if loop else 0)
    bgm_audio = bgm_input.audio.filter('volume', bgm_volume)
    if fade_in > 0:
        bgm_audio = bgm_audio.filter('afade', type='in', duration=fade_in)
    mixed = ffmpeg.filter([input_video.audio, bgm_audio], 'amix',
                          inputs=2, duration='first')
```

BGM 路径解析优先级:
1. 直接路径 (`/abs/path/to/bgm.mp3`)
2. 自定义覆盖 (`data/bgm/filename`)
3. 内置默认 (`bgm/filename`)

### 7.4 HTML 叠加到视频

当 media_type 为 "video" 时，先叠加再配音:

```
原始视频 (ComfyUI 生成)
  + HTML 渲染层 (透明背景PNG, 含字幕/标题/装饰)
  = 叠加视频 (含视觉元素)
  + TTS 音频 (替换原音频)
  = 最终视频段
```

---

## 8. HTML 模板帧渲染

### 8.1 HTMLFrameGenerator

使用 **Playwright** (无头 Chromium) 渲染 HTML 模板到 PNG:

```python
class HTMLFrameGenerator:
    def __init__(self, template_path):
        self.template = self._load_template(template_path)
        self.width, self.height = parse_template_size(template_path)
        # "1080x1920/default.html" → (1080, 1920)

    async def generate_frame(self, title, text, image, ext, output_path):
        context = {"title": title, "text": text, "image": image, **ext}
        html = self._replace_parameters(self.template, context)

        browser = await self._ensure_browser()  # 共享 Chromium 实例
        page = await browser.new_page(viewport=(width, height))
        await page.goto(file://tmp.html, wait_until='networkidle')
        await page.screenshot(path=output_path, omit_background=True)
```

### 8.2 模板 DSL

HTML 模板支持变量替换和自定义参数:

```html
<!-- 内置变量 -->
<h1>{{title}}</h1>
<p>{{text}}</p>
<img src="{{image}}">

<!-- 自定义参数 (支持类型声明) -->
<div style="color: {{accent_color:color=#3498db}}">
<span>{{subtitle:text=默认副标题}}</span>
<span>{{show_badge:bool=true}}</span>
```

### 8.3 Media Size 元标签

模板通过 meta 标签声明媒体尺寸:

```html
<meta name="template:media-width" content="1024">
<meta name="template:media-height" content="1024">
```

Pipeline 自动解析这些标签来确定 ComfyUI 生成图片/视频的分辨率。

### 8.4 模板类型智能检测

```python
def get_template_type(template_name):
    # "image_default.html"  → "image"   (需要 ComfyUI)
    # "video_default.html"  → "video"   (需要 ComfyUI 视频)
    # "static_default.html" → "static"  (纯文字，跳过所有媒体生成)
    # "asset_default.html"  → "static"  (素材模式，不生成)
```

---

## 9. LLM 服务与结构化输出

### 9.1 核心实现

```python
class LLMService:
    async def __call__(self, prompt, temperature=0.7, max_tokens=2000,
                       response_type=None, **kwargs):
        if response_type is not None:
            # 结构化输出模式
            return await self._call_with_structured_output(...)
        else:
            # 标准文本输出
            response = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=temperature, max_tokens=max_tokens
            )
            return response.choices[0].message.content
```

### 9.2 JSON Schema 注入方案

与 StructForge 相同，Pixelle-Video 也使用 **Schema 注入到 Prompt** 的方式:

```python
def _call_with_structured_output(self, client, model, prompt, response_type, ...):
    # 1. 生成 JSON Schema 指令
    json_schema_instruction = self._get_json_schema_instruction(response_type)
    # "## IMPORTANT: JSON Output Format Required
    #  You MUST respond with ONLY a valid JSON object...
    #  ```json
    #  {"type": "object", "properties": {...}}"
    #  ```"

    # 2. 追加到 prompt 末尾
    enhanced_prompt = f"{prompt}\n\n{json_schema_instruction}"

    # 3. 调用 LLM
    response = await client.chat.completions.create(...)

    # 4. 解析响应 (三重回退)
    return self._parse_response_as_model(content, response_type)
```

### 9.3 JSON 解析三重回退

```python
def _parse_response_as_model(self, content, response_type):
    # 回退1: 直接 parse
    try: return response_type.model_validate(json.loads(content))
    except: pass

    # 回退2: 提取 ```json ``` 代码块
    match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', content)
    if match: return response_type.model_validate(json.loads(match.group(1)))

    # 回退3: 提取第一个 { 到最后一个 }
    brace_start = content.find('{')
    brace_end = content.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        return response_type.model_validate(json.loads(content[brace_start:brace_end+1]))

    raise ValueError("Failed to parse LLM response")
```

### 9.4 兼容的 LLM 提供商

Pixelle-Video 通过 OpenAI SDK 兼容所有 OpenAI-API 格式的提供商:
- OpenAI (gpt-4o, gpt-4o-mini)
- 阿里 Qwen (qwen-max, qwen-plus)
- Anthropic Claude (通过兼容代理)
- DeepSeek (deepseek-chat)
- Ollama (本地免费模型)
- 任何 OpenAI-compatible API

---

## 10. 提示词工程体系

### 10.1 提示词文件组织

```
pixelle_video/prompts/
├── topic_narration.py       # 主题→旁白
├── content_narration.py     # 内容→旁白
├── image_generation.py      # 旁白→图片提示词
├── video_generation.py      # 旁白→视频提示词
├── style_conversion.py      # 风格转换
├── title_generation.py      # 标题生成
└── asset_script_generation.py  # 素材→分镜脚本
```

### 10.2 图片提示词生成 (关键)

```
# Role: 专业视觉创意设计师
# Input: {narrations_json}  (N段旁白)
# Output: {image_prompts: [N段英文图片提示词]}

要求:
- 语言必须为英文 (给 AI 生成模型用)
- 结构: 构图 + 视觉风格 + 光线 + 情绪
- 长度: 30-60 英文词
- 精准匹配旁白内容
```

### 10.3 视频提示词生成

```
# Role: 专业视频创意设计师
# 侧重动态元素

要求:
- 必须包含: 场景 + 角色动作 + 摄影机运动 + 情绪 + 氛围
- 动态词汇: moving, running, flowing, transforming
- 摄影机: camera pan, zoom in/out, tracking shot, aerial view
- 转场: transition, fade in/out, dissolve
```

### 10.4 Asset Script Generation (素材分镜)

```
# Input: intent + duration + assets_text (素材描述列表)
# Output: VideoScript (Pydantic structured output)

要求:
- LLM 直接分配素材到场景 (不需要复杂匹配逻辑)
- 每场景 1-3 句旁白
- 场景时长 ≈ 总时长 / 场景数
- 可以复用素材
```

### 10.5 Prompt 辅助函数

```python
def build_image_prompt(base_prompt, prompt_prefix):
    """组合前缀和基础提示词"""
    if prompt_prefix:
        return f"{prompt_prefix}, {base_prompt}"
    return base_prompt
```

支持用户在 API 层面自定义 `prompt_prefix` 来控制图片风格。

---

## 11. 数据模型

### 11.1 核心模型关系

```
StoryboardConfig (分镜配置)
  ├─ task_id: 任务隔离 ID
  ├─ n_storyboard: 分镜数量
  ├─ media_width/height: 媒体分辨率 (从模板 meta 解析)
  ├─ tts_inference_mode: "local" | "comfyui"
  ├─ voice_id: TTS 音色
  ├─ tts_speed: 语速 (0.5-2.0)
  ├─ media_workflow: 媒体生成工作流
  ├─ video_fps: 帧率
  └─ frame_template: HTML 模板路径

Storyboard (完整分镜板)
  ├─ title: 视频标题
  ├─ config: StoryboardConfig
  ├─ frames: List[StoryboardFrame]
  ├─ content_metadata: ContentMetadata (可选)
  ├─ final_video_path: 最终视频路径
  └─ total_duration: 总时长

StoryboardFrame (单帧)
  ├─ index: 0-based 索引
  ├─ narration: 旁白文本
  ├─ image_prompt: 图片/视频提示词
  ├─ audio_path: TTS 音频路径
  ├─ media_type: "image" | "video" | None
  ├─ image_path: 原始图片路径
  ├─ video_path: 原始视频路径
  ├─ composed_image_path: HTML 合成后 PNG
  ├─ video_segment_path: 最终视频段路径
  └─ duration: 时长 (来自 TTS 音频)

VideoGenerationResult (最终结果)
  ├─ video_path: 最终视频路径
  ├─ storyboard: 完整分镜板
  ├─ duration: 总时长
  ├─ file_size: 文件大小 (bytes)
  └─ created_at: 创建时间

MediaResult (媒体生成结果)
  ├─ media_type: "image" | "video"
  ├─ url: 媒体 URL/路径
  └─ duration: 时长 (仅视频)
```

### 11.2 故事板状态属性

```python
@property
def is_completed(self) -> bool:
    """所有帧都生成了视频段"""
    return all(f.video_segment_path is not None for f in self.frames)

@property
def progress(self) -> float:
    """处理进度 0.0-1.0"""
    completed = sum(1 for f in self.frames if f.video_segment_path is not None)
    return completed / len(self.frames) if self.frames else 0.0
```

---

## 12. API 层

### 12.1 端点设计

```
POST /api/video/generate/sync   → 同步生成 (阻塞至完成)
POST /api/video/generate/async  → 异步生成 (返回 task_id)
GET  /api/tasks/{task_id}       → 查询任务进度
GET  /api/files/{task_id}/...   → 访问生成的文件
```

### 12.2 同步 vs 异步

- **同步**: 直接返回 `VideoGenerateResponse` (video_url, duration, file_size)，适合短视频
- **异步**: 返回 `VideoGenerateAsyncResponse` (task_id)，后台执行，客户端轮询

### 12.3 文件服务

`path_to_url()` 函数将本地路径转换为 HTTP URL:
```
Windows: G:\...\output\20251205_233630_c939\final.mp4
       → http://localhost:8000/api/files/20251205_233630_c939/final.mp4
```

### 12.4 请求参数 (VideoGenerateRequest)

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| text | str | 必填 | 输入文本 (主题或脚本) |
| mode | "generate"/"fixed" | "generate" | 处理模式 |
| n_scenes | int | 5 | 分镜数 (仅 generate) |
| frame_template | str | None | HTML 模板路径 |
| media_workflow | str | None | 媒体生成工作流 |
| tts_workflow | str | None | TTS 工作流 |
| prompt_prefix | str | None | 图片风格前缀 |
| bgm_path | str | None | 背景音乐路径 |
| bgm_volume | float | 0.3 | BGM 音量 |
| template_params | dict | None | 自定义模板参数 |
| video_fps | int | 30 | 帧率 |

---

## 13. 与 StructForge 对比分析

### 13.1 定位差异

| 维度 | Pixelle-Video | StructForge |
|------|:---:|:---:|
| 核心场景 | "一句话生成视频" | "爆款结构迁移" |
| 输入 | 任意文本/主题/脚本 | 参考视频 + 新产品描述 |
| 素材来源 | AI 生成 (ComfyUI) 或用户上传 | 原视频素材 + AI 补全 |
| 核心竞争力 | 端到端 AI 视频生成 | 爆款结构分析 → 迁移到新产品 |
| 用户群 | 内容创作者、自媒体 | 电商运营、品牌方 |

### 13.2 架构对比

| 维度 | Pixelle-Video | StructForge |
|------|:---|:---|
| 管道模式 | **Template Method** (8步生命周期) | 顺序函数调用 |
| 状态管理 | **PipelineContext** dataclass | 分散在函数参数中 |
| 帧处理 | **FrameProcessor** (统一入口) | compositor.py 内联逻辑 |
| 进度上报 | **ProgressEvent** + 回调链 | poll-based 状态查询 |
| 媒体生成 | **ComfyKit** 统一抽象 (ComfyUI + RunningHub) | 直接 API 调用 |
| TTS | **双模式** (Edge TTS + ComfyUI TTS) | Edge TTS 为主 |
| 模板渲染 | **Playwright HTML → PNG** | 直接 FFmpeg drawtext |
| 持久化 | **文件系统 JSON** (PersistenceService) | SQLite |
| 配置 | **YAML + 热重载** | Pydantic Settings (.env) |
| 任务隔离 | `output/{task_id}/` 目录 | DB 中的 job 记录 |

### 13.3 关键差异

**Pixelle-Video 的优势**:

1. **TTS 驱动时长**: 从源头杜绝音画不同步 — StructForge 当前是"先定时长→再生成音频"，存在不匹配风险
2. **HTML 模板渲染**: Playwright 渲染 HTML 模板 → 更丰富的视觉效果（渐变、背景图、动画效果在帧中体现）；StructForge 直接用 FFmpeg drawtext 字幕 → 简单但灵活度低
3. **统一 FrameProcessor**: 每帧处理逻辑完全一致，4步子流程清晰；StructForge 的 compositor.py 行数过多，逻辑分散
4. **Template Method 管道**: 子类只需覆写特定步骤；StructForge 的每个流程是独立的函数
5. **媒体生成的 ComfyKit 抽象**: 同一套 API 支持自建 ComfyUI + RunningHub 云端 + API 直调；StructForge 只支持 API 直调
6. **PipelineContext 统一状态**: 步骤间传递清晰；StructForge 用函数参数 + 返回值传递
7. **文件系统持久化**: 可手动查看/调试；StructForge SQLite 不直观

**StructForge 的优势**:

1. **结构分析**: 对参考视频的场景分类、情绪曲线、节奏检测 — Pixelle-Video 没有
2. **素材匹配**: 智能匹配用户素材到分镜 — Pixelle-Video 的 AssetBasedPipeline 是 LLM 分配
3. **爆款审计**: 多维度评分 — Pixelle-Video 没有
4. **前端审核面板**: Director's Cut 交互 — Pixelle-Video 没有用户审核流程
5. **数据库查询**: SQLite 支持复杂查询和统计分析 — Pixelle-Video 文件系统需要重建索引
6. **平台差异化**: Kling/Runway/Seedance 多平台提示词 — Pixelle-Video 统一通过 ComfyKit

### 13.4 可直接借鉴的设计

| Pixelle-Video 模式 |  StructForge 对应改造 |
|------|------|
| Template Method Pipeline | `VideoRenderPipeline` 已有 7 步，可以用 PipelineContext 替代分散状态 |
| TTS 驱动时长 | `compositor.py` 改为先生成 TTS → 获取时长 → 再定分镜实际时长 |
| HTML Frame Rendering | 已有 `_render_prompt_card_html`，可以扩展为模板系统 |
| FrameProcessor 统一入口 | `compositor.py` 拆分 per-segment 处理逻辑 |
| ProgressEvent 回调链 | SSE + EventSource 替代 polling |
| JSON 解析三重回退 | `llm_client.py` 增加 code block 提取回退 |
| 模板 type 检测 | 参考 `get_template_type()` 实现智能跳过策略 |

---

## 14. 关键设计模式与启示

### 14.1 设计模式应用

| 模式 | 应用场景 |
|------|---------|
| **Template Method** | LinearVideoPipeline 定义骨架，子类实现步骤 |
| **Strategy** | 每个 Pipeline 是一个可替换的策略 |
| **Facade** | PixelleVideoCore 为所有服务提供统一入口 |
| **Observer** | ProgressEvent → callback 链传递进度 |
| **Lazy Initialization** | ComfyKit 按需创建，配置变更自动重建 |
| **Registry** | pipelines dict 动态注册管道 |
| **Context Object** | PipelineContext 封装整个执行生命周期状态 |

### 14.2 对 StructForge 的实战启示

1. **PipelineContext 优于分散参数**  
   当前 StructForge 在 render_pipeline.py 中已有 `RenderContext`，但可以进一步统一 — 分析阶段和迁移阶段也应当有自己的 Context 对象。

2. **TTS 驱动时长是"正确"的做法**  
   StructForge 当前是先估算分镜时长 → 生成 TTS → 速度调整。应该改为: 先生成 TTS → 获取实际时长 → 用此时长作为分镜实际时长 → 视频生成适配。

3. **HTML 模板系统大有可为**  
   当前 `_render_prompt_card_html` 已能用 Playwright 渲染卡片，可以发展为: 
   - 可配置的模板 (字幕位置/样式/动画)
   - 多分辨率支持 (从模板路径自动解析)
   - 模板参数 DSL (`{{accent_color:color=#ff0000}}`)

4. **JSON Schema 注入已在两边都实现**，但 Pixelle-Video 的**三重回退解析**更健壮。

5. **进度系统可升级**  
   从 polling → EventSource/SSE，每个步骤发送 `ProgressEvent`，前端实时显示子阶段。

6. **文件系统隔离是正确做法**  
   每次渲染任务独占目录 `output/{job_id}/`，方便调试和手动检查中间产物。

7. **RunningHub 并行模式值得学习**  
   当多个分镜需要 AI 生成时，可以用 asyncio.Semaphore 控制并发度并行处理。

---

## 附录: 文件索引

| 文件 | 行数 | 核心职责 |
|------|:---:|------|
| `pipelines/base.py` | 117 | BasePipeline 抽象基类 |
| `pipelines/linear.py` | 162 | LinearVideoPipeline + PipelineContext |
| `pipelines/standard.py` | 518 | StandardPipeline (通用流程) |
| `pipelines/asset_based.py` | 1056 | AssetBasedPipeline (用户素材) |
| `pipelines/custom.py` | 562 | CustomPipeline 模板 |
| `service.py` | 315 | PixelleVideoCore 服务层 |
| `services/frame_processor.py` | 505 | 每帧 4 步处理 |
| `services/media.py` | 318 | MediaService (图片/视频生成) |
| `services/tts_service.py` | 318 | TTSService (本地+ComfyUI) |
| `services/video.py` | 1004 | VideoService (FFmpeg 合成) |
| `services/frame_html.py` | 476 | HTMLFrameGenerator (Playwright 渲染) |
| `services/llm_service.py` | 343 | LLMService (OpenAI SDK + 结构化输出) |
| `services/persistence.py` | 675 | PersistenceService (文件系统) |
| `models/storyboard.py` | 143 | Storyboard 数据模型 |
| `models/media.py` | 61 | MediaResult 数据模型 |
| `utils/content_generators.py` | 502 | 内容生成工具函数 |
| `prompts/video_generation.py` | 133 | 视频提示词模板 |
| `prompts/asset_script_generation.py` | 81 | 素材分镜提示词模板 |
| `api/routers/video.py` | 290 | API 端点 |
| `api/schemas/video.py` | 116 | API Schema |
| `config/manager.py` | ~ | 配置管理器 (YAML + 热重载) |

---

## 15. 提示词工程体系 (完整)

### 15.1 七大提示词模板

| 提示词 | 输入 | 输出 | LLM 调用时机 |
|------|------|------|------|
| `topic_narration` | 主题/话题 | N 段旁白 (JSON) | StandardPipeline.generate_content (generate模式) |
| `content_narration` | 用户内容 | N 段旁白 (JSON) | StandardPipeline.generate_content (content模式) |
| `title_generation` | 内容 | 标题 (纯文本) | StandardPipeline.determine_title |
| `image_generation` | N 段旁白 | N 段图片提示词 (JSON) | StandardPipeline.plan_visuals |
| `video_generation` | N 段旁白 | N 段视频提示词 (JSON) | 视频模式 (plan_visuals) |
| `style_conversion` | 风格描述 | 英文图片风格前缀 | 用户自定义风格 |
| `asset_script_generation` | 意图+素材列表 | VideoScript (Pydantic) | AssetBasedPipeline.generate_content |

### 15.2 Image Prompt Generation 详解

这是最关键的一个提示词 — 决定 ComfyUI 生成的图片质量:

```python
IMAGE_PROMPT_GENERATION_PROMPT = """# Role: 专业视觉创意设计师
# Input: {"narrations": [...]}  (N 段旁白)
# Output: {"image_prompts": [...]}  (N 段英文图片提示词)

关键要求:
- 语言: 必须英文 (AI 图生模型需要)
- 结构: scene + character action + emotion + symbolic elements
- 长度: 50-100 英文词
- 风格: 不使用 literal 描述，多用象征手法可视化抽象概念
- 每个 prompt 必须唯一且创造性
"""
```

**内置三种风格预设**:

```python
IMAGE_STYLE_PRESETS = {
    "stick_figure": "火柴人草图, 黑白线条, 纯白背景, 极简手绘风格",
    "minimal":      "极简抽象艺术, 几何形状, 干净构图, 柔和粉彩色调",
    "concept":      "概念视觉隐喻, 象征性元素, 发人深省的意象, 艺术诠释",
}
```

### 15.3 Prompt Prefix 叠加机制

LLM 输出的 prompt 是 "基础版"，config 中的 `prompt_prefix` 是 "风格层":

```python
# 1. LLM 生成基础提示词 (反映旁白内容)
base_prompt = "A person standing at a crossroads, symbolizing life choices..."

# 2. config.yaml 中配置的风格前缀
prompt_prefix = "Minimalist black-and-white matchstick figure style, clean lines"

# 3. build_image_prompt() 合并
final_prompt = f"{prompt_prefix}, {base_prompt}"
# → "Minimalist black-and-white matchstick figure style, clean lines,
#    A person standing at a crossroads, symbolizing life choices..."
```

### 15.4 Video Prompt Generation 的区别

与 Image Prompt 的关键差异:
- ✅ 强调**动态**: moving, running, flowing, transforming
- ✅ 摄影机语言: camera pan, zoom in/out, tracking shot, aerial view
- ✅ 转场: transition, fade in/out, dissolve
- ✅ 氛围变化: lighting changes, shadows moving, sunlight streaming

---

## 16. ProgressEvent 进度系统

Pixelle-Video 用统一的 dataclass 传递所有进度信息:

```python
@dataclass
class ProgressEvent:
    event_type: str            # "generating_narrations" | "frame_step" | "concatenating"
    progress: float            # 0.0-1.0
    frame_current: int | None  # 当前帧号 (1-based)
    frame_total: int | None    # 总帧数
    step: int | None           # 帧内子步骤 1-4 (audio/image/compose/video)
    action: str | None         # "audio" | "image" | "compose" | "video"
    extra_info: str | None     # 附加信息
```

**对 StructForge 的启示**: 当前 StructForge 用 polling (每1秒查DB)，应该换成 SSE + ProgressEvent 回调链。每段分镜处理的 3 步 (resolve→render→assemble) 各发一个 ProgressEvent。

---

## 17. 模板系统深度分析

### 17.1 模板命名约定

```
templates/{WIDTH}x{HEIGHT}/
  ├── image_*.html   → 需要 AI 生图 ({{image}} 变量会被替换为图片)
  ├── video_*.html   → 需要 AI 生视频
  └── static_*.html  → 纯文字模板 (不调用 ComfyUI)
  └── asset_*.html   → 用户素材模板 (AssetBasedPipeline)
```

### 17.2 模板类型检测

```python
def get_template_type(name: str) -> Literal['static', 'image', 'video']:
    if name.startswith("static_"): return "static"    # 跳过媒体生成
    elif name.startswith("video_"): return "video"    # ComfyUI 视频
    elif name.startswith("image_"): return "image"    # ComfyUI 图片
    else: return "image"  # 默认
```

这个设计让 Pipeline 可以**智能跳过**不需要的媒体生成:
- `static_*` 模板 → 不调 ComfyUI → 快 10 倍 + 零成本
- `image_*` 模板 → 调 ComfyUI 生图
- `video_*` 模板 → 调 ComfyUI 生视频

### 17.3 Media Size Meta Tags

```html
<meta name="template:media-width" content="1024">
<meta name="template:media-height" content="1024">
```

HTMLFrameGenerator 解析这些标签 → 告诉 ComfyUI 应该生成什么分辨率的图片/视频。

### 17.4 模板 DSL

```html
<!-- 内置变量 -->
<h1>{{title}}</h1>          <!-- 视频标题 -->
<p>{{text}}</p>              <!-- 旁白文本 -->
<img src="{{image}}">        <!-- AI 生成的图片 -->

<!-- 自定义参数 (支持类型和默认值) -->
{{accent_color:color=#3498db}}   <!-- 颜色参数, 默认蓝色 -->
{{show_badge:bool=true}}          <!-- 布尔参数 -->
{{subtitle:text=默认副标题}}       <!-- 文本参数, 带默认值 -->
{{duration:number=5}}             <!-- 数字参数 -->
```

### 17.5 资源覆盖系统

```
搜索优先级:
1. data/{resource_type}/*  (用户自定义, 高优先级)
2. {resource_type}/*        (默认, 低优先级)

例如模板: data/templates/1080x1920/my_theme.html → templates/1080x1920/my_theme.html
```

用户可以把自定义模板放在 `data/templates/` 下，不会被 git 覆盖。BGM 和工作流同样支持。

### 17.6 内置模板一览

Pixelle-Video 自带了 **20+** 个专业设计的 HTML 模板:

| 模板 | 风格 |
|------|------|
| `image_default.html` | 简洁书本风格, L形角标, 引号装饰 |
| `image_modern.html` | 现代渐变色设计 |
| `image_elegant.html` | 优雅暗色调 |
| `image_cartoon.html` | 卡通风格 |
| `image_neon.html` | 霓虹灯赛博朋克 |
| `image_healing.html` | 治愈系暖色调 |
| `image_psychology_card.html` | 心理学知识卡片 |
| `image_full.html` | 全屏背景大图 |
| `asset_default.html` | 用户素材展示模版 |

---

## 18. 配置系统架构

### 18.1 Pydantic 配置层级

```
PixelleVideoConfig (顶层)
├── project_name: str
├── llm: LLMConfig
│   ├── api_key, base_url, model
├── api_providers: APIProvidersConfig
│   ├── common, openai, dashscope, deepseek, gemini, ark, kling
├── comfyui: ComfyUIConfig
│   ├── comfyui_url, runninghub_api_key, runninghub_concurrent_limit
│   ├── tts: TTSSubConfig
│   │   ├── inference_mode ("local" | "comfyui")
│   │   ├── local: {voice, speed}
│   │   └── comfyui: {default_workflow}
│   ├── image: ImageSubConfig
│   │   ├── default_workflow
│   │   └── prompt_prefix
│   └── video: VideoSubConfig
│       ├── default_workflow
│       └── prompt_prefix
└── template: TemplateConfig
    └── default_template
```

### 18.2 配置热重载

```python
# 每次读取配置时从 config_manager 动态获取
def _get_config_value(self, key, default=None):
    from pixelle_video.config import config_manager
    return getattr(config_manager.config.llm, key, default)
```

不是单次读取后缓存 — 每次 LLM 调用都会从 `config_manager` 重新读取。配合 YAML 文件监控可以实现零重启更新配置。

### 18.3 ComfyKit 懒加载 + 热重载

```python
async def _get_or_create_comfykit(self):
    current_config = self._get_comfykit_config()
    current_hash = md5(json.dumps(current_config))

    if self._comfykit is None or self._comfykit_config_hash != current_hash:
        # 配置变更 → 关闭旧实例 → 创建新实例
        if self._comfykit:
            await self._comfykit.close()
        self._comfykit = ComfyKit(**current_config)
        self._comfykit_config_hash = current_hash
    return self._comfykit
```

对 StructForge 的启示: ComfyUIService 也可以用这个模式，支持在运行时切换 RunningHub API Key 或 ComfyUI URL。

---

## 19. Edge TTS 实现细节

### 19.1 重试与限流

```python
_RETRY_COUNT = 5           # 最多重试 5 次
_MAX_RETRY_DELAY = 10.0     # 最大重试延迟 10s
_REQUEST_DELAY = 0.5        # 请求前最小间隔
_MAX_CONCURRENT_REQUESTS = 3 # 最大并发数
```

**指数退避 + 随机抖动**:
```python
exponential_delay = retry_base_delay * (2 ** (attempt - 1))
jitter = random.uniform(0, retry_base_delay)
retry_delay = min(exponential_delay + jitter, _MAX_RETRY_DELAY)
```

**全局信号量限流**: 用 `asyncio.Semaphore(3)` 限制同时进行的 TTS 请求数，防止触发 Microsoft 的 401 限流。

### 19.2 错误分类处理

- `WSServerHandshakeError` / `ClientResponseError` → 重试
- `NoAudioReceived` → 重试 + 额外 2s 延迟
- 其他异常 → 立即抛出，不重试

### 19.3 certifi SSL 证书

```python
ssl_context = ssl.create_default_context(cafile=certifi.where())
```

用 certifi 的证书包而非关闭 SSL 验证，兼顾安全性和兼容性。

---

## 20. 任务隔离文件系统

### 20.1 目录结构

```
output/{task_id}/
├── final.mp4              # 最终视频
├── frames/
│   ├── 01_audio.mp3       # TTS 音频
│   ├── 01_image.png       # ComfyUI 生图
│   ├── 01_composed.png    # HTML 合成图 (含字幕)
│   ├── 01_segment.mp4     # 最终视频段
│   ├── 02_audio.mp3
│   └── ...
├── metadata.json           # 任务元数据
├── storyboard.json         # 分镜板数据
└── .index.json             # 全局任务索引
```

### 20.2 task_id 生成

```python
def create_task_id():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"{timestamp}_{random_suffix}"
    # → "20250609_224855_a3f2"
```

碰撞概率 < 0.0001% (每秒 65536 种组合)。

### 20.3 帧文件命名

```python
def get_task_frame_path(task_id, frame_index, file_type):
    filename = f"{frame_index + 1:02d}_{file_type}.{ext}"
    return f"{task_dir}/frames/{filename}"
    # → "output/20250609_224855_a3f2/frames/01_audio.mp3"
    # → "output/20250609_224855_a3f2/frames/03_segment.mp4"
```

所有中间产物可追溯、可调试。

---

## 21. 对 StructForge 的新增建议

基于以上完整分析，对之前文档的补充:

### 21.1 模板系统可以立即借鉴

StructForge 当前只有 `prompt_card.html` 一个模板。可以直接从 Pixelle-Video 复制/改编:
- `image_default.html` → StructForge 的分镜展示模板 (替换 Pillow 渲染的蓝图卡片)
- `image_modern.html` → CTA/Hook 段的视觉增强模板
- 模板 DSL + 参数系统 → 让模板可配置

### 21.2 提示词系统可以分层

当前 StructForge 的迁移提示词 (migrator.py) 是一个巨大的 prompt (100+ 行)。可以拆分为:
1. 结构分析 prompt (从参考视频提取结构)
2. 产品映射 prompt (将结构映射到新产品)
3. 视觉提示词 prompt (为每段生成可喂给 ComfyUI 的英文 prompt)

### 21.3 任务隔离立即可用

当前 StructForge 用 `output/{project_id}/.work-{job_id}/`，已经接近 Pixelle-Video 模式。加上:
- `metadata.json` (任务完整参数)
- `storyboard.json` (分镜板数据)
- 命名从 `segment_000.mp4` 改为 `01_segment.mp4` (更可读)

### 21.4 配置的热重载

当前 StructForge 的 `Settings` 从 `.env` 读取一次后不再更新。可以:
- 为 RunningHub Key 等敏感配置支持运行时更新
- ComfyUIService 已实现了 hash 检测 → 自动重建

---

> **结论**: Pixelle-Video 的视频生成架构是教科书级的 Template Method 模式应用。其最核心的三个设计决策 — TTS 驱动时长、HTML 模板渲染、PipelineContext 状态管理 — 直接解决了视频生成领域最棘手的音画同步、视觉效果、流程可维护性问题。StructForge 已经在 `render_pipeline.py` 中借鉴了部分模式，下一步应重点引入 TTS 驱动时长、更完善的 PipelineContext 体系、多模板 HTML 渲染系统、和 RunningHub ComfyUI 集成。
