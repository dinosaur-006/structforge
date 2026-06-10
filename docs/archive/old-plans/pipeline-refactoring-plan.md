# StructForge 渲染管线重构方案

> 日期: 2026-06-09  
> 基于: Pixelle-Video LinearVideoPipeline + 当前 compositor.py  
> 状态: 待实施

---

## 0. 现状诊断

```
compositor.py 的 render() 方法: 621 行
Compositor 类的公开方法:    1 个 (render)
整个渲染逻辑:               1 个嵌套 5 层的巨型函数
```

当前 render() 中隐含的 8 个逻辑步骤全部内联在一个函数中。每步之间通过局部变量传递状态（`command`、`shot_used`、`segment_path`、`concatenated_output`），变量在 600 行中随时可能被任何分支修改。

---

## 1. 目标架构

### 1.1 整体结构

```
compositor.py (保留，标记 deprecated)
    └── Compositor.render() → 转发到 VideoRenderPipeline

render_pipeline.py (新建)
    ├── RenderContext          — 状态对象（替代散落的局部变量）
    ├── VideoRenderPipeline   — Template Method 编排器
    └── SegmentProcessor      — 单个分镜处理器
```

### 1.2 Template Method 步骤

```python
class VideoRenderPipeline:
    """视频渲染管线 — Template Method 模式"""

    async def run(self, job_id, project_id, version, resolution, script_version) -> RenderResult:
        ctx = RenderContext(job_id=job_id, project_id=project_id, ...)

        await self._prepare(ctx)              # 1. 加载脚本、创建工作目录
        await self._process_segments(ctx)      # 2. 逐分镜渲染（可并行化）
        await self._synthesize_speech(ctx)     # 3. TTS 合成（分镜级）
        await self._apply_overlays(ctx)        # 4. 动画叠加层
        await self._assemble_video(ctx)        # 5. 拼接 + 转码
        await self._mix_audio(ctx)             # 6. BGM 混音 + 卡点对齐
        await self._finalize(ctx)              # 7. 保存输出、更新状态
        return ctx.result
```

---

## 2. 详细设计

### 2.1 RenderContext — 状态数据类

```python
@dataclass
class RenderContext:
    """渲染管线状态对象。替代 render() 中 20+ 个局部变量。"""

    # 输入参数
    job_id: str
    project_id: str
    version: str
    resolution: str
    width: int = 1080
    height: int = 1920

    # 加载的数据
    script: FinalScript | None = None
    assets: dict[str, dict] = field(default_factory=dict)

    # 工作目录
    work_dir: Path | None = None
    output_dir: Path | None = None

    # 分镜渲染状态
    segments: list[Any] = field(default_factory=list)
    segment_files: list[Path] = field(default_factory=list)

    # 音频
    tts_engine: Any = None
    bgm_engine: Any = None

    # 动画
    render_engine: Any = None

    # 输出
    output_path: Path | None = None

    # 诊断
    warnings: list[str] = field(default_factory=list)
    progress: float = 0.0
```

### 2.2 VideoRenderPipeline — 编排器

```python
class VideoRenderPipeline:
    """StructForge 视频渲染管线。

    使用 Template Method 模式将 621 行 render() 拆分为
    7 个独立的、可测试的、可覆写的方法。
    """

    def __init__(self, repository: SQLiteRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self._segment_processor = SegmentProcessor(settings)

    # ═══════════════════════════════════════════════
    # Template Method — 主入口
    # ═══════════════════════════════════════════════

    async def run(self, **kwargs) -> RenderContext:
        ctx = RenderContext(**kwargs)

        await self._prepare(ctx)              # Step 1
        await self._process_segments(ctx)     # Step 2
        await self._synthesize_speech(ctx)    # Step 3
        await self._apply_overlays(ctx)       # Step 4
        await self._assemble_video(ctx)       # Step 5
        await self._mix_audio(ctx)            # Step 6
        await self._finalize(ctx)             # Step 7
        return ctx

    # ═══════════════════════════════════════════════
    # Step 1: 准备工作
    # ═══════════════════════════════════════════════

    async def _prepare(self, ctx: RenderContext) -> None:
        """加载脚本、验证结构、创建工作目录、解析素材。"""
        self.repository.update_render_job(ctx.job_id, status="processing", progress=5)

        # 加载 FinalScript
        script_payload = (
            self.repository.get_script_version(ctx.project_id, ctx.script_version)
            if ctx.script_version
            else self.repository.get_project_script(ctx.project_id)
        )
        if not script_payload:
            raise CompositorError("Project has no FinalScript")

        ctx.script = FinalScript.model_validate(script_payload)
        _validate_restructure_decision(ctx.script)

        # 解析资源
        ctx.assets = {a["id"]: a for a in self.repository.list_assets(ctx.project_id)}
        ctx.width, ctx.height = RESOLUTIONS.get(ctx.resolution, RESOLUTIONS["1080p"])
        ctx.work_dir = self.settings.output_dir / ctx.project_id / f".work-{ctx.job_id}"
        ctx.output_dir = self.settings.output_dir / ctx.project_id
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        # 获取分镜列表
        ctx.segments = _segments_for_version(ctx.script, ctx.version)
        if not ctx.segments:
            raise CompositorError("FinalScript has no renderable segments")

        ctx.warnings.append(f"渲染管线启动: {len(ctx.segments)} 个分镜")

    # ═══════════════════════════════════════════════
    # Step 2: 逐分镜渲染
    # ═══════════════════════════════════════════════

    async def _process_segments(self, ctx: RenderContext) -> None:
        """处理每个分镜：寻源 → 渲染 → 输出分镜 MP4 片段。"""
        total = len(ctx.segments)

        for idx, segment in enumerate(ctx.segments):
            self.repository.update_render_job(
                ctx.job_id,
                progress=10 + (idx / max(total, 1)) * 60,
                warnings=[f"渲染分镜 {idx + 1}/{total}"],
            )
            seg_path = self._segment_processor.process(
                segment=segment,
                index=idx,
                script=ctx.script,
                assets=ctx.assets,
                work_dir=ctx.work_dir,
                width=ctx.width,
                height=ctx.height,
                version=ctx.version,
                settings=self.settings,
                warnings=ctx.warnings,
            )
            ctx.segment_files.append(seg_path)

    # ═══════════════════════════════════════════════
    # Step 3: TTS 语音合成
    # ═══════════════════════════════════════════════

    async def _synthesize_speech(self, ctx: RenderContext) -> None:
        """分镜级 TTS 合成，音频时长驱动分镜时长。"""
        self.repository.update_render_job(ctx.job_id, progress=75, warnings=ctx.warnings)
        tts = TTSEngine(
            endpoint=self.settings.tts_endpoint or None,
            api_key=self.settings.tts_api_key,
            voice=self.settings.tts_voice,
            speed=self.settings.tts_speed,
        )
        ctx.tts_engine = tts

        if not tts.available:
            ctx.warnings.append("TTS 未配置")
            return

        tts_ok = 0
        for idx, segment in enumerate(ctx.segments):
            seg_text = _strip_production_params(segment.script or "")
            if not seg_text.strip():
                continue

            seg_path = ctx.segment_files[idx]
            tts_path = ctx.work_dir / f"segment_{idx:03d}_tts.mp3"
            seg_dur = max(segment.duration, 0.5)

            if tts.synthesize(seg_text, tts_path, target_duration=seg_dur):
                tts_ok += 1
                actual_dur = _probe_duration(tts_path)
                if actual_dur > 0:
                    segment.duration = max(actual_dur, 0.5)

                # 智能合并
                mixed = ctx.work_dir / f"segment_{idx:03d}_mixed.mp4"
                _merge_video_audio_smart(str(seg_path), str(tts_path), str(mixed))
                if mixed.exists() and mixed.stat().st_size > 0:
                    mixed.replace(seg_path)
                    ctx.segment_files[idx] = seg_path

        if tts_ok > 0:
            # Reflow 时间线
            cursor = 0.0
            for seg in ctx.segments:
                seg.start = cursor
                seg.duration = max(seg.duration, 0.5)
                seg.end = cursor + seg.duration
                cursor = seg.end
            ctx.warnings.append(f"TTS: {tts_ok}/{len(ctx.segments)} 分镜 (total={cursor:.1f}s)")

    # ═══════════════════════════════════════════════
    # Step 4: 动画叠加层
    # ═══════════════════════════════════════════════

    async def _apply_overlays(self, ctx: RenderContext) -> None:
        """为 Hook/CTA 分镜叠加 Remotion/Pillow 动画。"""
        engine = RendererFactory.create(
            remotion_url=getattr(self.settings, 'remotion_service_url', None),
            ffmpeg_path=self.settings.ffmpeg_path,
            engine="auto",
        )
        for idx, seg in enumerate(ctx.segments):
            if seg.type in ("cta", "hook") and seg.script:
                clean = _strip_production_params(seg.script)
                overlay_path, reason = engine.render_for_segment(
                    segment_type=seg.type, script_text=clean,
                    output_dir=ctx.work_dir, duration=min(seg.duration, 2.5),
                )
                if overlay_path:
                    seg_in = ctx.segment_files[idx]
                    mixed = ctx.work_dir / f"segment_{idx:03d}_animated.mp4"
                    _run_ffmpeg_overlay(str(seg_in), overlay_path, str(mixed))
                    if mixed.exists() and mixed.stat().st_size > 0:
                        mixed.replace(seg_in)
                        ctx.segment_files[idx] = seg_in

    # ═══════════════════════════════════════════════
    # Step 5: 拼接视频
    # ═══════════════════════════════════════════════

    async def _assemble_video(self, ctx: RenderContext) -> None:
        """FFmpeg concat 所有分镜 → 输出单个 MP4。"""
        self.repository.update_render_job(ctx.job_id, progress=80, warnings=ctx.warnings)
        output = ctx.output_dir / f"{ctx.version}.mp4"

        if len(ctx.segment_files) > 1:
            parts = "".join(f"[{i}:v][{i}:a]" for i in range(len(ctx.segment_files)))
            inputs = [arg for sp in ctx.segment_files for arg in ("-i", str(sp))]
            _run_ffmpeg([
                self.settings.ffmpeg_path, "-y", *inputs,
                "-filter_complex", f"{parts}concat=n={len(ctx.segment_files)}:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ])
        elif len(ctx.segment_files) == 1:
            _run_ffmpeg([
                self.settings.ffmpeg_path, "-y",
                "-i", str(ctx.segment_files[0]),
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ])

        ctx.output_path = output

    # ═══════════════════════════════════════════════
    # Step 6: BGM 混音
    # ═══════════════════════════════════════════════

    async def _mix_audio(self, ctx: RenderContext) -> None:
        """BGM 混音 + 节拍卡点对齐。"""
        self.repository.update_render_job(ctx.job_id, progress=90, warnings=ctx.warnings)
        bgm = BGMEngine(
            bgm_dir=getattr(self.settings, 'bgm_library_dir', None),
            ffmpeg_path=self.settings.ffmpeg_path,
        )
        tracks = bgm.list_tracks()
        if not tracks:
            ambient = ctx.work_dir / "ambient_bgm.mp3"
            if bgm.generate_ambient(ambient, duration=ctx.script.total_duration + 3):
                tracks = [{"id": "ambient", "name": "Ambient", "path": str(ambient),
                           "duration": ctx.script.total_duration, "category": "minimal"}]

        if tracks:
            track = tracks[0]
            # Beat alignment
            beats = bgm.detect_beats(track["path"], ctx.script.total_duration + 3)
            snapped = 0
            if beats:
                for seg in ctx.segments:
                    nearest = min(beats, key=lambda b: abs(b - seg.start))
                    if abs(nearest - seg.start) <= 0.15:
                        seg.start = nearest
                        snapped += 1
            if snapped:
                ctx.warnings.append(f"Beat aligned: {snapped}/{len(ctx.segments)}")

            # Mix BGM
            bgm_out = ctx.work_dir / f"{ctx.version}_bgm.mp4"
            try:
                _run_ffmpeg(bgm.mix_command(
                    input_video=ctx.output_path, bgm_path=track["path"],
                    output_video=bgm_out,
                    volume=getattr(self.settings, 'bgm_volume', 0.08),
                    duration=ctx.script.total_duration,
                ))
                if bgm_out.exists() and bgm_out.stat().st_size > 0:
                    final = ctx.output_dir / f"{ctx.version}.mp4"
                    bgm_out.rename(final)
                    ctx.output_path = final
            except Exception:
                ctx.warnings.append("BGM mixing failed")

    # ═══════════════════════════════════════════════
    # Step 7: 最终化
    # ═══════════════════════════════════════════════

    async def _finalize(self, ctx: RenderContext) -> None:
        """更新渲染任务状态、保存输出路径。"""
        self.repository.update_render_job(
            ctx.job_id,
            status="completed",
            progress=100,
            output_path=f"/outputs/{ctx.project_id}/{ctx.version}.mp4",
            warnings=ctx.warnings,
        )
```

### 2.3 SegmentProcessor — 分镜处理器

```python
class SegmentProcessor:
    """处理单个分镜：寻源 → 渲染 → 输出片段 MP4。"""

    def process(self, segment, index, script, assets, work_dir,
                width, height, version, settings, warnings) -> Path:
        seg_path = work_dir / f"segment_{index:03d}.mp4"
        ass_path = work_dir / f"segment_{index:03d}.ass"
        dur = _output_duration(segment.duration, version, segment.type)
        ass_path.write_text(_ass_for_segment(segment, version, dur), encoding="utf-8")

        asset = assets.get(segment.asset_id) if segment.asset_id else None
        source_path = Path(asset["file_path"]) if asset and asset.get("file_path") else None

        # 路由到对应的渲染策略
        if source_path is None or not source_path.exists():
            return self._render_no_asset(segment, index, script, work_dir, seg_path, ass_path, dur, width, height, version, settings, warnings)
        elif asset["type"] == "image":
            return self._render_image(segment, asset, source_path, seg_path, ass_path, dur, width, height, version, settings, warnings)
        else:
            return self._render_video(segment, asset, source_path, script, seg_path, ass_path, dur, width, height, version, settings, warnings)

    def _render_no_asset(self, ...):
        """无素材分镜 → AI 提示词卡片或 packaging 卡片。"""
        ...

    def _render_image(self, ...):
        """图片素材 → 静态图片转视频。"""
        ...

    def _render_video(self, ...):
        """视频素材 → 片段提取/重组/AI 生成。"""
        ...
```

---

## 3. 与现有代码的关系

### 3.1 零破坏策略

```
compositor.py:
  class Compositor:
      def render(self, ...):
          # 转发到新管线
          pipeline = VideoRenderPipeline(self.repository, self.settings)
          loop = asyncio.new_event_loop()
          loop.run_until_complete(pipeline.run(...))
```

旧的 `Compositor.render()` 保留在代码中，标记 `# deprecated`。路由层通过配置开关切换新旧：

```python
# config.py
STRUCTFORGE_USE_NEW_PIPELINE = True  # 默认使用新管线
```

### 3.2 复用的函数（不重复实现）

以下函数从 `compositor.py` 导出，在新管线中直接 import 使用：

| 函数 | 用途 | 状态 |
|------|------|------|
| `build_image_command` | 构建 FFmpeg 图片→视频命令 | ✅ 直接复用 |
| `build_video_command` | 构建 FFmpeg 视频命令 | ✅ 直接复用 |
| `build_placeholder_command` | 构建 FFmpeg 占位命令 | ✅ 直接复用 |
| `_cinematic_motion` | 运镜 zoompan 计算 | ✅ 直接复用 |
| `_apply_visual_fx` | 特效滤镜 | ✅ 直接复用 |
| `_emotion_color_grade` | 情绪色调 | ✅ 直接复用 |
| `_ass_for_segment` | ASS 字幕生成 | ✅ 直接复用 |
| `_version_filters` | 版本滤镜 | ✅ 直接复用 |
| `_merge_video_audio_smart` | 智能音视频合并 | ✅ 直接复用 |
| `_probe_duration` | 探测媒体时长 | ✅ 直接复用 |
| `_render_prompt_card_html` | HTML 提示词卡片 | ✅ 直接复用 |

### 3.3 文件结构

```
ai-services/services/
  compositor.py          — 现有代码（保留，标记 deprecated）
  render_pipeline.py     — 新建：VideoRenderPipeline + RenderContext
  segment_processor.py   — 新建：SegmentProcessor
  frame_renderer.py      — 已建：HTML 模板渲染器
```

---

## 4. 实施步骤

### Step 1: 创建 RenderContext 和 VideoRenderPipeline 骨架 (30min)

1. 新建 `render_pipeline.py`
2. 定义 `RenderContext` dataclass
3. 定义 `VideoRenderPipeline` 类 + 7 个空方法
4. 验证导入无错误

### Step 2: 迁移 _prepare (30min)

从 `render()` lines 47-70 提取逻辑到 `_prepare()`。

### Step 3: 创建 SegmentProcessor + 迁移分镜渲染 (60min)

1. 新建 `segment_processor.py`
2. 从 `render()` lines 72-430 提取三个渲染路径
3. `_render_no_asset` — packaging / AI prompt card / placeholder
4. `_render_image` — 图片转视频
5. `_render_video` — 视频片段处理

### Step 4: 迁移 _synthesize_speech (20min)

从 `render()` lines 442-515 提取 TTS 逻辑（已重构为分镜级）。

### Step 5: 迁移 _apply_overlays (15min)

从 `render()` lines 507-570 提取动画叠加逻辑。

### Step 6: 迁移 _assemble_video + _mix_audio + _finalize (30min)

从 `render()` lines 572-670 提取拼接、BGM、最终化逻辑。

### Step 7: 添加路由开关 + 测试 (30min)

1. `Compositor.render()` 增加配置开关
2. 运行现有 54 个测试确认零 regression
3. 新增 5-8 个 Pipeline 单元测试

---

## 5. 验收标准

| # | 标准 | 验证方法 |
|---|------|---------|
| 1 | 54 个现有测试全部通过 | `pytest` 全量 |
| 2 | 新旧管线产出相同视频 | 同输入 → 同输出 MP4 |
| 3 | 每个 step 方法 < 80 行 | 代码审查 |
| 4 | SegmentProcessor 可单独实例化测试 | 单元测试 |
| 5 | 配置开关可切换新旧 | 修改 config 后重启 |

---

## 6. 工时估算

| 步骤 | 工时 |
|------|------|
| Step 1: 骨架 | 0.5h |
| Step 2: _prepare | 0.5h |
| Step 3: SegmentProcessor | 1.0h |
| Step 4: _synthesize_speech | 0.3h |
| Step 5: _apply_overlays | 0.3h |
| Step 6: assemble + BGM + finalize | 0.5h |
| Step 7: 路由 + 测试 | 0.5h |
| **总计** | **3.5h** |
