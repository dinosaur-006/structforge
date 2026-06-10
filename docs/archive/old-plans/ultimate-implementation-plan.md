# StructForge 终极优化实施计划

> 版本: 1.0  
> 日期: 2026-06-09  
> 基于: Pixelle-Video 深度代码分析 + 全部已知 Bug 修复  
> 状态: 待实施

---

## 0. 前置条件

### 当前已确认正常工作的模块

```
✅ 视频上传 & ASR 转写
✅ Vision 关键帧分析  
✅ LLM 结构提取 (Doubao Seed)
✅ 爆款审计 (32项指标)
✅ LLM 脚本迁移 (三层防御: auto-wrap + duration修复 + ID映射)
✅ Pre-viz 全局指示器
✅ 提示词 TXT 导出
✅ LLMOutagePanel 中断面板
✅ 后端 47 tests 全通过
```

### 当前已知问题

```
🔴 TTS 语速不匹配分镜时长 → 语音截断
🔴 原视频音频残留 → 与 TTS 重叠 
🔴 无素材分镜黑屏 → 提示词卡片不可达
🟡 FFmpeg 滤镜链 Bug (sin/crop 兼容性)
🟡 compositor.render() 300+ 行巨型函数
🟡 没有"一键 AI 全填充"路径 B
```

---

## 1. 实施总览

| Phase | 主题 | 文件 | 工时 | 优先级 |
|-------|------|------|------|--------|
| **A** | 音画同步反转 (TTS 驱动时长) | `compositor.py` + `migrator.py` | 2h | 🔴 P0 |
| **B** | 消除音频重叠 | `compositor.py` | 0.5h | 🔴 P0 |
| **C** | 提示词卡片可达 | `migrator.py` + `compositor.py` | 0.5h | 🔴 P0 |
| **D** | HTML 模板动效系统 | `frame_html.py` (新建) + `compositor.py` | 4h | 🟡 P1 |
| **E** | 智能音视频合成 | `video.py` (移植) | 2h | 🟡 P1 |
| **F** | Pipeline 模式重构 | `compositor.py` | 4h | 🟢 P2 |
| **G** | 验收测试 | 全部 | 2h | 🔴 P0 |

---

## 2. Phase A: 音画同步反转 (P0)

### 2.1 目标

将当前"分镜时长固定 → TTS 被动适配"改为"TTS 音频时长 → 决定分镜最终时长"。

### 2.2 核心逻辑

```
当前:
  structure → segments[i].duration = 固定值(继承原视频)
  TTS → 文本 → 合成音频 → 拆分到各分镜 → 截断/加速

改为:
  structure → segments[i].duration = 固定值(继承原视频)  ← 仅作初始参考
  TTS → 文本 → 合成音频 → 获取各分镜实际音频时长
  各分镜 final_duration = max(音频时长, 最小阈值)       ← 音频驱动
  后续分镜 start/end 自动推移                            ← reflow
```

### 2.3 实施步骤

**文件: `ai-services/services/compositor.py`**

**Step A1**: 在 TTS 合成后、分片前，获取每个分镜的实际 TTS 时长

```python
# 在 tts.synthesize() 之后，拆分 TTS 之前

# 方案: 分镜级别 TTS (每段单独合成)
for idx, segment in enumerate(segments):
    seg_text = _strip_production_params(segment.script or "")
    if seg_text.strip():
        seg_tts_path = work_dir / f"segment_{idx:03d}_tts_raw.mp3"
        seg_dur = max(segment.duration, 0.5)
        if tts.synthesize(seg_text, seg_tts_path, target_duration=seg_dur):
            # 获取实际音频时长
            actual_dur = _probe_duration(seg_tts_path)
            # 用音频时长更新分镜 duration
            segment.duration = max(actual_dur, 0.5)
```

**Step A2**: TTS 合成从"全脚本合成再拆分"改为"分镜级合成"

```python
# 之前:
full_script = " ".join(...)
tts.synthesize(full_script, full_tts_path, target_duration=total_dur)
# 按固定 seg_dur 拆分

# 之后:
for segment in segments:
    seg_text = _strip_production_params(segment.script or "")
    tts.synthesize(seg_text, seg_tts_path, target_duration=segment.duration)
    # 不再拆分，每个分镜已有独立 TTS
```

**Step A3**: Reflow 后续分镜的时间线

在 TTS 改变了某些分镜的 duration 后，重新计算 start/end：

```python
cursor = 0.0
for seg in segments:
    seg.start = cursor
    seg.end = cursor + seg.duration
    cursor = seg.end
# 更新 total_duration
script.total_duration = cursor
```

**Step A4**: 画面内容适配新时长

```python
# 在 build_image_command / build_video_command 中
# duration 参数现在使用 TTS 驱动的实际时长
output_duration = _output_duration(segment.duration, version, segment.type)
```

### 2.4 向后兼容

如果 TTS 不可用（无 API Key），保持原有的固定时长逻辑不变。

### 2.5 验收标准

- 每个分镜的配音完整播放，最后一个字不截断
- 视频总时长可能比原视频长（因为音频驱动）
- TTS 不可用时，行为与修复前一致

---

## 3. Phase B: 消除音频重叠 (P0)

### 3.1 目标

参考视频原音轨绝不与新 TTS 配音混合。

### 3.2 实施步骤

**文件: `ai-services/services/compositor.py`**

**Step B1**: 已在 `build_video_command` 中增加 `-map 0:v -map 1:a`（上次修复）。**验证此修复已上线**。

**Step B2**: 在 TTS 已配置时，对参考视频分镜强制 `has_audio=False`：

```python
# 已实现（上次修复），确认逻辑:
if is_reference:
    keep_audio = False  # 参考视频永远静音
```

### 3.3 验收标准

- 导出视频中只能听到 TTS 配音 + BGM
- 原视频人声完全消失

---

## 4. Phase C: 提示词卡片可达 (P0)

### 4.1 目标

无素材的 `aigc` 分镜在渲染时显示文生视频提示词卡片，不是黑屏。

### 4.2 当前状态（已修复，待验证上线）

| 修复 | 文件 | 行 | 状态 |
|------|------|-----|------|
| source 强制赋值 | `migrator.py` | 765 | ✅ |
| bound_assets 排除参考视频 | `migrator.py` | 742 | ✅ |
| shot_used 声明 | `compositor.py` | 93 | ✅ |
| FFmpeg -map 音频修复 | `compositor.py` | 848 | ✅ |

### 4.3 验证步骤

1. 删除旧数据库 `data/structforge.db`
2. 重启服务端
3. 上传视频 → 分析 → 直接生成脚本（不上传素材）→ 渲染
4. 终端应输出 `[COMPOSITOR] No-asset path for seg-xxx`
5. 视频中无素材分镜显示提示词卡片（非黑屏）

---

## 5. Phase D: HTML 模板动效系统 (P1)

### 5.1 目标

用 Playwright 渲染 HTML+CSS 动效替代 FFmpeg `drawtext`/`eq`/`crop` 滤镜链。

### 5.2 为什么需要

| 问题 | FFmpeg 滤镜 | HTML 模板 |
|------|-----------|---------|
| `sin()` 在 crop 中报错 | ❌ 已踩坑 | ✅ 不存在此问题 |
| 丰富动效 | ❌ 只有 zoompan/crop/drawtext | ✅ 完整 CSS animation |
| 调试难度 | ❌ 看 FFmpeg 报错信息 | ✅ 浏览器 F12 调试 |
| 新增模板 | ❌ 改 Python 代码 | ✅ 改 HTML+CSS |

### 5.3 实施步骤

**Step D1**: 新建 `ai-services/services/frame_renderer.py`

从 Pixelle-Video 的 `frame_html.py` 移植核心逻辑：

```python
class FrameRenderer:
    """HTML-based frame renderer using Playwright."""
    
    def __init__(self, template_path: str, width: int = 1080, height: int = 1920):
        self.template = self._load_template(template_path)
        self.width = width
        self.height = height
    
    async def render_frame(
        self,
        text: str,           # 字幕文案
        subtitle: str = "",  # 底部字幕
        image: str = "",     # 背景图片（可选）
        output_path: str = ""
    ) -> str:
        """Render HTML template to PNG frame."""
        html = self.template.replace("{{text}}", text)
        html = html.replace("{{subtitle}}", subtitle or text)
        # Playwright 渲染 → PNG
        ...
```

**Step D2**: 创建简化模板 `templates/prompt_card.html`

```html
<!DOCTYPE html>
<html><head>
<style>
body { width:1080px; height:1920px; background:#0A0A10;
       font-family:'PingFang SC',sans-serif; color:#E8E8ED; }
.prompt-box { padding:120px 80px; }
.prompt-text { font-size:42px; line-height:1.8; color:#00E676; }
.camera-info { font-size:28px; color:#FFB300; margin-top:60px; }
.cost-badge { position:fixed; top:40px; right:40px; font-size:24px; color:#8B8B9E; }
</style>
</head><body>
<div class="prompt-box">
  <div class="cost-badge">🟡 AI 生成预留位 | 预估 ${{cost}}</div>
  <div class="prompt-text">{{prompt_text}}</div>
  <div class="camera-info">🎥 {{camera}} | ✨ {{visual_fx}} | 🎬 {{duration}}s</div>
</div>
</body></html>
```

**Step D3**: 在 compositor 中替换 `render_blueprint_card` 调用

```python
# 之前:
from services.blueprint_renderer import render_blueprint_card
render_blueprint_card(path, segment_type=..., visual_prompt=..., ...)

# 之后:
from services.frame_renderer import FrameRenderer
renderer = FrameRenderer("templates/prompt_card.html")
renderer.render_frame(
    text=ai_result.prompt_text[:300],
    subtitle=ai_result.subtitle_text,
    image=None,
    output_path=str(prompt_card_path)
)
```

### 5.4 向后兼容

- Pillow `render_blueprint_card` 保留作为 Playwright 不可用时的 fallback
- Windows 上 Playwright 需要 `playwright install chromium`

---

## 6. Phase E: 智能音视频合成 (P1)

### 6.1 目标

从 Pixelle-Video 移植 `merge_audio_video()`，替代现有粗糙的 `amix:duration=first`。

### 6.2 实施步骤

**Step E1**: 在 `compositor.py` 中新增 `_merge_audio_video_smart()` 方法

```python
def _merge_audio_video_smart(
    video_path: str, audio_path: str, output_path: str,
    replace_audio: bool = True,
    pad_strategy: str = "freeze"  # "freeze" | "black"
) -> str:
    """智能合并音视频。音频长→冻结末帧填充。视频长→裁剪。"""
    import ffmpeg as _ffmpeg  # ffmpeg-python
    
    video_dur = _probe_duration(video_path)
    audio_dur = _probe_duration(audio_path)
    
    diff = video_dur - audio_dur
    
    if diff < 0:
        # 视频短 → pad
        pad_dur = -diff
        input_video = _ffmpeg.input(video_path)
        video_stream = input_video.video.filter(
            'tpad', stop_mode='clone', stop_duration=pad_dur
        )
        target_dur = audio_dur
    elif diff > 0.3:
        # 视频长 → trim
        input_video = _ffmpeg.input(video_path, t=audio_dur)
        video_stream = input_video.video
        target_dur = audio_dur
    else:
        # 容差内 → 无操作
        input_video = _ffmpeg.input(video_path)
        video_stream = input_video.video
        target_dur = video_dur
    
    input_audio = _ffmpeg.input(audio_path)
    audio_stream = input_audio.audio.filter('volume', 0.9)
    
    (_ffmpeg.output(video_stream, audio_stream, output_path,
                    vcodec='libx264', acodec='aac')
     .overwrite_output().run(quiet=True))
    
    return output_path
```

**Step E2**: 替换 TTS 混入逻辑

```python
# 之前:
cmd = ["ffmpeg", ..., "-filter_complex", "[1:a]volume=0.9[tts];[0:a][tts]amix=...", ...]

# 之后:
_merge_audio_video_smart(str(seg_path), str(tts_seg_path), str(mixed_path),
                         replace_audio=True, pad_strategy="freeze")
```

---

## 7. Phase F: Pipeline 模式重构 (P2)

### 7.1 目标

将 `compositor.render()` 从 300+ 行巨型函数重构为 Template Method 模式。

### 7.2 新结构

```python
class VideoRenderPipeline:
    """StructForge video render pipeline (Template Method pattern)."""
    
    async def render(self, ctx: RenderContext) -> RenderResult:
        await self._prepare_environment(ctx)      # 1. 创建 work_dir, 加载资源
        await self._process_segments(ctx)          # 2. 逐分镜渲染 (并行化)
        await self._synthesize_tts(ctx)            # 3. TTS 合成 (分镜级)
        await self._merge_audio(ctx)              # 4. 智能音视频合并
        await self._concat_videos(ctx)             # 5. 拼接所有分镜
        await self._mix_bgm(ctx)                  # 6. BGM 叠加
        await self._finalize(ctx)                 # 7. 输出 & 清理
        return ctx.result
    
    # 每个方法独立可测试，可被子类覆写
    async def _process_segments(self, ctx):
        for seg in ctx.segments:
            processor = SegmentProcessor(ctx)
            await processor.process(seg)
```

### 7.3 实施

- `compositor.py` 保留现有逻辑作为 `LegacyCompositor`
- 新建 `render_pipeline.py` 实现新架构
- 通过 config flag 切换（`use_new_pipeline=True`）
- 测试全部通过后替换旧实现

---

## 8. 实施顺序总览

```
第 1 天（3h）:
  Phase A: 音画同步反转     ← 解决 TTS 截断
  Phase B: 验证音频修复       ← 确认已上线
  Phase C: 验证提示词卡片     ← 确认已上线

第 2 天（4h）:
  Phase D: HTML 模板系统      ← 替代 FFmpeg 滤镜
  Phase E: 智能音视频合成     ← 移植 Pixelle video.py

第 3 天（4h）:
  Phase F: Pipeline 重构      ← 代码质量
  Phase G: 全面验收测试       ← 端到端验证
```

## 9. 验收清单

| # | 验收项 | 通过条件 |
|---|--------|---------|
| 1 | TTS 不截断 | 每个分镜配音播完最后一个字 |
| 2 | 无音频重叠 | 只能听到 TTS + BGM |
| 3 | 提示词卡片可见 | 无素材分镜显示文字提示词，不是黑屏 |
| 4 | 震屏不报错 | FFmpeg 不再出现 sin/crop 解析错误 |
| 5 | 47 tests 全过 | 零 regression |
| 6 | 端到端 10 分钟 | 上传→分析→生成→渲染→播放，全套 < 10min |
