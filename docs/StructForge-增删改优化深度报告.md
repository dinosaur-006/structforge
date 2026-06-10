# StructForge 增删改优化深度报告

> 基于全代码库 113 文件逐行审查 | 2026-06-10 | 从产品功能+体验+全流程可运行性出发

---

## 总览

| 类别 | 数量 | 说明 |
|------|:--:|------|
| 🗑️ 删除 | 10 模块 | 死代码/从未调用/已知冗余 |
| 🔧 修复 | 8 项 | 数据断链/Bug/对齐问题 |
| ⚡ 优化 | 12 项 | 功能正常但体验/性能可提升 |
| ✅ 保持 | ~40 模块 | 设计良好无需变动 |

---

## 一、🗑️ 需删除的模块 (10项)

### 1.1 `ai-services/services/remotion_client.py` (130行)

**证据**:
- 全代码库零导入 (`grep` 确认: 无任何文件 import 此模块)
- 文件自身 docstring 写明: *"NOTE (2026-06-10): This module is currently unused."*
- `renderer_abstraction.py` 的 `RendererFactory` 已完全替代了 Remotion 调用路径

**影响**: 零。删除不影响任何功能。

---

### 1.2 `ai-services/services/compositor.py` — 旧渲染路径 (约560行)

**证据**:
- `Compositor.render()` 第49行: `use_new = getattr(self.settings, 'use_new_pipeline', True)`
- 当 `use_new_pipeline=True` (默认), 立即转发到 `VideoRenderPipeline.run()` 并 return
- 第59行之后的全部旧代码 (~560行) **永远不会执行**
- 唯一被外部引用的函数 `_validate_restructure_decision`、`_segments_for_version` 等已被 `render_pipeline.py` 内联或重复导入

**操作**: 
- 保留 `Compositor` 类作为向后兼容壳 (仅转发到新管道)
- 删除第59行之后的旧渲染逻辑
- 将共享工具函数 (`build_image_command`, `_ass_for_segment`, `_strip_production_params` 等) 移入独立 `render_utils.py`

**影响**: 减少 560 行死代码，降低维护困惑。

---

### 1.3 `ai-services/services/optimization_pipeline.py` (306行) + 5个附属模块

**依赖链**:
```
routes/optimize.py → optimization_pipeline.py
  → phase0_structure.py (StructureOptimizer)
  → phase1_multimodal.py (ShotAnalyzer)
  → phase4_transitions.py
  → phase5_color.py
  → optimization_models.py (17个Pydantic模型)
```

**证据**:
- 前端 `api.runOptimization()` 存在于 `api.ts:289`，但**全前端代码零调用**
- 这是一个与主流程 (`AnalysisPipeline → MigratorService → VideoRenderPipeline`) **完全平行**的另一套管道
- 它做"结构优化+镜头匹配+转场规划+LUT色彩+AI生成"，与主流程功能高度重叠
- 唯一的 HTTP 端点 `POST /api/v1/optimize/{project_id}` 从未被触发

**操作**: 删除以下 6 个文件:
- `services/optimization_pipeline.py`
- `services/phase0_structure.py`
- `services/phase1_multimodal.py`
- `services/phase4_transitions.py`
- `services/phase5_color.py`
- `services/optimization_models.py`

同时删除 `routes/optimize.py` 中的 `POST /{project_id}` 端点 (保留 waveform/thumbnail/blueprint-payloads 端点)。

**影响**: 减少约 1200 行死代码，消除维护者"两套管道哪个是真的"的困惑。

---

### 1.4 `ai-services/services/prompt_engine/adapters/kling.py`

**证据**:
- Kling 适配器几乎无引用
- 系统实际使用 Seedance (doubao) + ComfyUI RunningHub (Flux/WAN)
- `prompt_engine/adapters/` 目录中 `seedance.py` 和 `runway.py` 是活跃的

**操作**: 删除 `kling.py`。如后续需要可随时恢复。

---

### 1.5 `src/components/migrate/GapPanel.tsx` — 前端孤立组件

**证据**:
- `GapPanel` 是一个完整实现的组件 (缺口列表 + 修复按钮)
- 但它只在自己的测试文件 `GapPanel.test.tsx` 中被 import
- `MigratePage.tsx` **没有引入** GapPanel — 用户在编辑页看不到缺口
- `MigratePage.tsx` 文案写"AI 已自动完成素材匹配和缺口补全"但用户无法查看或手动修复缺口

**操作**: **不在 MigratePage 中渲染 GapPanel**（缺口修复应该在编辑阶段完成后自动执行）。改为:
- 删除 `GapPanel.tsx` 和 `GapPanel.test.tsx`
- 或在 MigratePage 中添加一个可折叠的缺口状态摘要（非交互式，仅展示）

**当前建议**: 保留组件代码但**不渲染**，因为缺口修复在 `loadProjectStructure` 时自动完成。如果未来需要手动缺口管理再启用。

---

### 1.6 `render_pipeline.py:253` 死导入

**代码**:
```python
from services.frame_renderer import _render_prompt_card_html as _html_card
```

**证据**: `_html_card` 在 `_process_segments` 方法体中**从未被调用**。实际渲染走 `_generate_ai_visual()` → ComfyUI 或 Pillow blueprint 路径。

**操作**: 删除此行导入。

---

### 1.7 `compositor.py:1195` 死导入

**代码**:
```python
from services.frame_renderer import _render_prompt_card_html
```

**证据**: 这行在 `compositor.py` 的旧渲染路径中 (第59行之后)，该路径在 `use_new_pipeline=True` 时永不执行。

**操作**: 随 compositor.py 旧代码一并删除。

---

### 1.8 `frame_renderer.py` 评估 — 保留但标记

**状态**: `frame_renderer.py` 提供 `FrameRenderer` 类 (Playwright HTML→PNG)。目前只有死导入引用它。但 `blueprint_renderer.py` 已完全替代其功能 (Pillow直接渲染)。如果未来不需要 Playwright 渲染，可删除。

**建议**: 保留 `frame_renderer.py` 作为备用渲染方案，但移除所有死导入。

---

## 二、🔧 需修复的项 (8项)

### 2.1 🔴 Pydantic 校验阻断 — coverImagePath / highlightMoments / shot_pool 数据断链

**严重度**: 高 — 后端生成的数据永远无法到达前端

**根因**: `pipeline.py` 在分析完成后将 `coverImagePath`、`highlightMoments`、`shot_pool` 注入 `result_json` 的 dict 中:

```python
# pipeline.py L198-204
result_with_cover = dict(existing["result"])
meta = dict(result_with_cover.get("meta") or {})
meta["coverImagePath"] = str(cover_path)
result_with_cover["meta"] = meta
self.repository.update_job(job_id, result=result_with_cover)
```

但当 API 返回时，FastAPI 会用 `VideoStructure.model_validate()` 校验。`VideoMeta` 是 `StrictModel(extra="forbid")`，所以 `coverImagePath` 会触发 **Pydantic ValidationError**。

同样 `highlightMoments` 和 `shot_pool` 作为顶层额外字段也会被 `StrictModel(extra="forbid")` 拒绝。

**修复方案**:
- 方案A (推荐): 在 `VideoMeta` 中添加可选字段 `coverImagePath: str | None = None`
- 在 `VideoStructure` 中添加可选字段 `highlightMoments: list[dict] | None = None` 和 `shot_pool: list[dict] | None = None`
- 同步更新前端 `types.ts` 中的 `VideoMeta` 接口

---

### 2.2 🔴 前端 types.ts 缺少 `Capabilities.videoGeneration`

**严重度**: 中 — SettingsPage 运行时不出错 (通过 Record 动态访问)，但类型不安全

**根因**: 
- 后端 `main.py:152` 返回 `videoGeneration: CapabilityItem | None`
- 前端 `types.ts:105-111` 的 `Capabilities` 接口不包含 `videoGeneration`
- `SettingsPage.tsx:35` 通过 `caps.videoGeneration?.detail` 动态访问 (绕过了类型检查)

**修复**: 在 `types.ts` 的 `Capabilities` 接口中添加:
```typescript
videoGeneration?: CapabilityItem;
```

---

### 2.3 🟡 前端 `Project.thumbnail` 字段不存在

**严重度**: 低 — HistoryPage 使用了 `p._duration` 和 `p._segmentCount` 但后端从不返回

**根因**: `HistoryPage.tsx` 定义了 `ProjectWithMeta = Project & { _duration?: number; _segmentCount?: number }`，但后端 `ProjectOut` 模型不含这些字段。`_duration` 和 `_segmentCount` 永远是 `undefined`。

**修复**: 要么在后端 `ProjectOut` 中添加这些统计字段，要么删除前端对这些字段的引用 (`p._duration?.toFixed(0)` 和 `p._segmentCount`)。

---

### 2.4 🟡 `render_pipeline.py` TTS 索引变量错误

**严重度**: 中 — 运行时错误

**代码** (`render_pipeline.py:464-468`):
```python
if not tts.available:
    ctx.warnings.append("TTS 未配置 — 视频将仅有背景音乐")
    # Mark all segments as having no TTS
    for seg in ctx.segments:
        ctx.tts_paths[idx] = None  # ← BUG: idx 来自外层循环, 此处未定义!
    return
```

`idx` 在这个 `if` 块中未定义 (它只存在于下面的 `for idx, segment in enumerate(ctx.segments)` 循环中)。

**修复**:
```python
for i in range(len(ctx.segments)):
    ctx.tts_paths[i] = None
```

---

### 2.5 🟡 AnalyzePage 无法展示 BurstAuditPanel

**严重度**: 低 — 组件存在但用户看不到

**根因**: `AnalyzePage.tsx` 引入了 `StructureTabs` 和 `VideoInfoCard`，但没有引入 `BurstAuditPanel`。审计数据通过 `/api/v1/audit/{jobId}` 端点可用，但用户需要自己知道去访问。

**修复**: 在 `AnalyzePage` 的分析结果展示中添加 BurstAuditPanel，或在 `StructureTabs` 中增加"爆款审计"标签页。

---

### 2.6 🟡 HistoryPage 导航失效场景

**严重度**: 中 — 用户体验断裂

**根因**: `HistoryPage.tsx:125` 所有项目卡片点击后统一跳转到 `/result/${p.id}`。但如果项目状态是 `draft` 或 `analyzing`，ResultPage 会因为没有脚本数据而显示错误。

**修复**: 根据项目状态路由到不同页面:
- `draft/analyzing` → `/analyze?projectId=${p.id}`
- `editing` → `/migrate/${p.id}`
- `completed/rendering` → `/result/${p.id}`

---

### 2.7 🟡 `FinalScript.segments[].visual_requirements` 前端类型缺失

**严重度**: 低 — 后端 schema 有，前端类型无

**修复**: 在 `types.ts` 的 `FinalSegment` 接口中添加:
```typescript
visual_requirements?: Record<string, string>;
```

---

### 2.8 🟡 渲染失败诊断信息不持久

**严重度**: 中 — 用户刷新页面后看不到失败原因

**根因**: `render_pipeline.py` 的异常信息只写入 `render_jobs.error` 字段。前端 `pollRenderJob` 将其写入 store，但 store 只持久化 `sidebarCollapsed` 和 `currentVersionId`。页面刷新后 render 失败信息丢失。

**修复**: 将 `renderError` 也加入 store 的 `partialize` 持久化列表，或使用 `sessionStorage` (store 第714行已有 `sessionStorage.setItem('lastRenderError', ...)` 但 `pollRenderJob` 未读取它)。

---

## 三、⚡ 需优化的项 (12项)

### 3.1 `VideoRenderPipeline._process_segments` — 分支逻辑过于复杂

**现状**: `_process_segments` 方法约200行，包含6层嵌套 if-else 处理"无素材/图片素材/视频素材/参考视频/AIGC跳过"等场景。

**优化**: 提取策略模式——每个分支独立为一个 `_render_*_segment` 方法:
- `_render_ai_visual_segment()` — 无素材 → ComfyUI/Pillow
- `_render_image_asset_segment()` — 图片素材
- `_render_video_asset_segment()` — 视频素材
- `_render_reference_segment()` — 参考视频

**预期**: 可读性提升 3x，单元可测。

---

### 3.2 `MigratorService._build_prompt` — 提示词过长

**现状**: `_build_prompt()` 生成 ~5000+ 字符的提示词，包含完整的 JSON 示例和重复说明。每次 LLM 调用消耗大量 token。

**优化**: 
- 将 `timelineSpec` 的完整 JSON 示例移到 schema 描述中 (作为 `FinalScript.model_json_schema()` 的一部分)
- 将分镜类型详解 (Hook/Pain/Product/Proof/CTA 的5段说明) 压缩为要点列表
- 将品牌调性推断逻辑从前端提示词移到后端代码

**预期**: 提示词减少 30-40%，token 消耗同比降低。

---

### 3.3 `BurstMetricsCalculator` — EXPERIMENTAL 指标清理

**现状**: `burst_metrics.py` 中有2个指标标记为 `EXPERIMENTAL_METRICS` (H-T2 和 C-S2)，在评分计算中被排除。

**优化**: 要么完成这两个实验指标 (补充数据源和算法)，要么删除它们。保留"实验性"代码在 production 中是不好的实践。

---

### 3.4 `MigratePage` 缺少缺口状态展示

**现状**: 用户在编辑页看不到素材缺口的实际状况。文案只说"AI 已自动完成"但没有可视化反馈。

**优化**: 在 AssetPanel 下方添加一个紧凑的缺口状态摘要 (非交互式):
```
✅ Hook段已匹配 · ⚠️ Product段需要AI生成 · ✅ CTA段已覆盖
```
或直接展示 `gaps.filter(g => g.status === 'open').length` 的数量。

---

### 3.5 `ResultPage` ReviewPanel 应独立文件

**现状**: `ReviewPanel` 组件 (~160行) 定义在 `ResultPage.tsx` 底部 (第482-657行)。它是 `Director's Cut` 审核面板——产品核心差异化功能。

**优化**: 提取为 `src/components/result/ReviewPanel.tsx`，便于独立测试和维护。

---

### 3.6 `AppLayout` 快捷键提示实现

**现状**: `AppLayout.tsx:154` 用 `alert()` 展示快捷键列表。这是最简单的实现但体验差。

**优化**: 使用 Modal 或 Drawer 组件展示快捷键列表，支持键盘 `?` 键触发 (对标 Notion/Figma 等产品)。

---

### 3.7 `TTSEngine` 缺少进度反馈

**现状**: TTS 合成 N 个分镜的音频时，用户看不到进度。`_synthesize_all_tts` 只在全部完成后汇报。

**优化**: 通过 `repository.update_render_job(warnings=[...])` 推送实时进度: "TTS: 3/7 分镜已完成"。

---

### 3.8 `ComfyUIService` 图片下载无重试

**现状**: `render_pipeline.py:126` 用 `urllib.request.urlretrieve()` 下载 Flux 生成的图片，失败即抛异常。

**优化**: 添加指数退避重试 (2次，1s/3s)，RunningHub 的临时 URL 可能偶发失败。

---

### 3.9 `BGMEngine.generate_ambient` — 空白 BGM 生成

**现状**: 当 `bgm_library_dir` 未配置时，`generate_ambient()` 创建静默音频。用户体验差。

**优化**: 预置 2-3 首免版权背景音乐 (可从 Pixabay/Mixkit 获取)，在 Docker 构建时嵌入。

---

### 3.10 `WorkflowSteps` — 步骤不可点击导航

**现状**: 4步进度条 (分析→编辑→生成→结果) 仅展示状态，不能点击跳转。

**优化**: 已完成步骤可点击跳转。当前步骤高亮。未来步骤灰显。用户可在已完成的步骤间自由导航。

---

### 3.11 `AnalyzePage` — 多样例融合入口缺失

**现状**: `SampleComparison` 组件支持多样例比较，但"融合选中样例"功能的前端触发按钮和后端 API 未对接。

**优化**: 在 `SampleComparison` 中添加"融合选中"按钮，调用 `POST /api/v1/structure/{project_id}/fusion` (端点已在 plan 中设计但未实现)。

---

### 3.12 SSE 实时进度推送未在前端启用

**现状**: 后端有 SSE 端点:
- `GET /api/v1/analyze/{job_id}/stream` (分析进度)
- `GET /api/v1/render/{job_id}/stream` (渲染进度)

但前端仍使用轮询 (`setInterval` 每秒 poll)。

**优化**: 前端改用 `EventSource` 监听 SSE 流，减少不必要的 HTTP 请求，获得更实时的进度更新 (特别是阶段详情)。

---

## 四、✅ 保持不变的模块

以下模块设计良好，功能正确，无需变动:

**核心分析**: `pipeline.py` (AnalysisPipeline) — 缓存+多模态+结构提取流程完整
**脚本生成**: `migrator.py` (MigratorService) — LLM重试+fallback+后处理链完整
**视频渲染**: `render_pipeline.py` (VideoRenderPipeline) — 7步Template Method模式清晰
**缺口系统**: `gap_detector.py` + `gap_filler.py` — 4策略检测修复完整
**评分引擎**: `burst_metrics.py` (41指标) + `burst_auditor.py` (LLM审计)
**结构编辑**: `structure_editor.py` (undo/redo持久化)
**素材系统**: `asset_analyzer.py` + `asset_matcher.py` (LLM匹配)
**NL编辑**: `nl_editor.py` — 自然语言结构修改
**TTS引擎**: `tts_engine.py` — Edge TTS + 火山双引擎
**ComfyUI**: `comfyui_service.py` — RunningHub集成完整
**提示词引擎**: `prompt_engine/` (engine/assembler/validator/vocabulary) — 模块化清晰
**数据层**: `repository.py` + `schemas.py` — 完整CRUD+迁移
**API层**: 全部8个路由文件 — RESTful设计规范
**前端状态**: `store/index.ts` — 36 actions 覆盖完整
**前端API**: `services/api.ts` — 30方法 + 重试 + LLM outage检测
**UI组件**: 13个基础组件 — 设计统一
**页面**: AnalyzePage/MigratePage/ResultPage/ProjectListPage/HistoryPage/SettingsPage — 功能完整
**设计系统**: `tailwind.config.js` + `index.css` — Swiss spa主题一致

---

## 五、执行优先级建议

| 优先级 | 类别 | 项数 | 预计工时 |
|------|------|:--:|:--:|
| P0 | 🔧 修复 — 阻断性 Bug (2.1/2.4/2.6) | 3 | 2h |
| P1 | 🔧 修复 — 数据断链 (2.2/2.3/2.5/2.7/2.8) | 5 | 3h |
| P2 | 🗑️ 删除 — 死代码清理 | 7 | 1h |
| P3 | ⚡ 优化 — 体验提升 (3.4/3.5/3.7/3.9/3.10) | 5 | 4h |
| P4 | ⚡ 优化 — 架构改进 (3.1/3.2/3.3/3.6/3.8/3.11/3.12) | 7 | 6h |

**总计**: ~16h 完成全部增删改优化，产品将达到"全模块对齐、全流程可跑、零死代码"状态。
