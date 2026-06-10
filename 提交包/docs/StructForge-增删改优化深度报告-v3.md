# StructForge 增删改优化深度报告 v3

> 基于 v2 产品分析报告的二次深度审查 | 2026-06-10
> 方法论：逐方法/逐端点/逐组件验证调用链 + 数据生产消费匹配

---

## 总览

| 类别 | 数量 | 说明 |
|------|:--:|------|
| 🗑️ 删除 | 12 项 | 零引用死代码 + 残留方法 + 孤立组件 |
| 🔧 修复 | 4 项 | 功能断裂/配置缺陷/UX断层 |
| ⚡ 优化 | 6 项 | 体验提升/架构改进 |

---

## 一、🗑️ 需删除的项 (12项)

### 1.1 后端死代码 (1文件)

#### `ai-services/services/frame_renderer.py` (127行)

**证据**:
- 全代码库 `grep` 确认：**零 import 引用**
- 原先被 `compositor.py:1193` 和 `render_pipeline.py:253` 死导入引用
- 两处死导入已在 v2 优化中清除 → 该文件彻底无引用
- 功能已被 `blueprint_renderer.py` (Pillow 直接渲染) 完全替代

**操作**: 删除 `frame_renderer.py`

---

### 1.2 前端孤立组件 (3文件)

#### `src/components/migrate/GapPanel.tsx` + `GapPanel.test.tsx`

**证据**:
- `grep` 确认：仅 `GapPanel.test.tsx` import `GapPanel`
- 零页面/组件渲染该组件
- v2 优化已在 `MigratePage.tsx` 中添加内联缺口摘要 (轻量替代)
- GapPanel 功能 (缺口列表+手动修复按钮) 与当前"AI自动修复"设计理念冲突

**操作**: 删除 `GapPanel.tsx` 和 `GapPanel.test.tsx`

#### `src/mocks/projects.ts`, `mocks/gaps.ts`, `mocks/versions.ts`, `mocks/assets.ts` (4文件)

**证据**:
- `grep` 确认：**零 import 引用**
- 仅有 `mockAnalysisResult` 被 store 和测试文件使用
- 这4个 mock 文件从未被任何代码导入

**操作**: 删除这4个 mock 文件。保留 `mockAnalysisResult.ts`

---

### 1.3 前端死 API 方法 (7个方法)

**检测方法**: 遍历 `src/services/api.ts` 全部 30 个方法，对每个方法执行：
1. `grep` 检查是否在 `src/store/index.ts` 中被调用
2. `grep` 检查是否在 `src/pages/` 或 `src/components/` 中被直接调用
3. 两次检查均无结果 → 标记为死方法

**检测结果**:

| API 方法 | store调用 | 组件直接调用 | 后端端点 | 判定 |
|------|:--:|:--:|------|:--:|
| `listTemplates()` | ❌ | ❌ | ✅ 存在 | 🗑️ |
| `listPipelines()` | ❌ | ❌ | ✅ 存在 | 🗑️ |
| `previewMedia()` | ❌ | ❌ | ✅ 存在 | 🗑️ |
| `migrateVariant()` | ❌ | ❌ | ✅ 存在 | 🗑️ |
| `runOptimization()` | ❌ | ❌ | ❌ 已删除 | 🗑️ |
| `getProject()` | ❌ | ❌ | ✅ 存在 (store用listProjects替代) | 🗑️ |
| `replaceStructure()` | ❌ | ❌ | ✅ 存在 (store用updateSegments替代) | 🗑️ |
| `addSegment()` | ❌ | ❌ | ✅ 存在 | 🗑️ |
| `upgradeSegmentToVideo()` | ❌ | ❌ | ✅ 存在 | ⚠️ 保留(未来WAN2.2) |
| `getVideoUpgradeStatus()` | ❌ | ❌ | ✅ 存在 | ⚠️ 保留(未来WAN2.2) |

**操作**: 从 `api.ts` 中删除 7 个死方法:
- `listTemplates`, `listPipelines`, `previewMedia`, `migrateVariant`, `runOptimization`, `getProject`, `replaceStructure`, `addSegment`

同步删除 `store/index.ts` 中可能引用这些方法的 dead actions (检查确认无引用)。

同步删除 `api.test.ts` 中针对 `migrateVariant` 的测试用例 (第114行)。

---

### 1.4 后端死端点 (建议删除的端点)

部分后端端点对应的前端 API 方法已被标记为删除，但这些端点的删除需谨慎评估：

| 端点 | 前端状态 | 建议 |
|------|:--:|------|
| `POST /api/v1/image/generate` | 无前端 API 方法 | ⚠️ 保留 (后端内部使用/CLI工具) |
| `POST /api/v1/migrate/{id}/variant` | `migrateVariant` 死方法 | ⚠️ 保留 (未来多版本对比) |
| `POST /api/v1/render/{id}/upgrade-to-video/` | `upgradeSegmentToVideo` 死方法 | ⚠️ 保留 (WAN 2.2 roadmap) |
| `GET /api/v1/render/upgrade-status/{id}` | 同上 | ⚠️ 保留 |
| `GET /api/v1/templates` | `listTemplates` 死方法 | ⚠️ 保留 (外部集成可能用) |
| `GET /api/v1/pipelines` | `listPipelines` 死方法 | ⚠️ 保留 (外部集成可能用) |
| `GET /api/v1/analyze/{id}/stream` | SSE 未启用 | ⚠️ 保留 (优化项 3.1) |
| `GET /api/v1/render/{id}/stream` | SSE 未启用 | ⚠️ 保留 (优化项 3.1) |
| `GET /api/v1/audit/{id}/template` | 无方法 | ⚠️ 保留 (模板复用) |

**本次不删除任何后端端点**。这些端点要么有明确的未来用途 (WAN 2.2/SSE)，要么为外部集成预留。

---

## 二、🔧 需修复的项 (4项)

### 2.1 🔴 SSE 实时推送未启用

**严重度**: 中 — 用户体验受影响，前端无意义轮询浪费资源

**现状**:
- 后端已实现两个 SSE 端点 (v1 开发):
  - `GET /api/v1/analyze/{job_id}/stream` — 推送分析进度+子阶段
  - `GET /api/v1/render/{job_id}/stream` — 推送渲染进度+阶段+警告
- 前端 `store/index.ts` 中 `startAnalysis` 和 `pollRenderJob` 仍使用 `setInterval` 每秒轮询

**修复方案**:
- `store.startAnalysis()`: 将 `while(true) + await wait(1000)` 替换为 `EventSource`
- `store.pollRenderJob()`: 同样替换为 SSE
- SSE 断线时自动重连，超时后回退到轮询

**影响**: 分析/渲染进度更新延迟从 ~1000ms 降至 ~100ms，减少 ~300 次无意义 HTTP 请求/任务

---

### 2.2 🟡 `content_safety.py` 配置死锁

**严重度**: 低 — 默认关闭，但代码完整

**现状**:
- `ContentSafetyService` 在 `migrator.py` 中被导入和实例化
- 但执行被 `if self.settings.content_safety_enabled:` 守卫
- `config.py` 中 `content_safety_enabled: bool = False` (默认关闭)
- 且 `content_safety_blocked_terms: str = ""` (空字符串)
- 没有任何 UI 或文档告知用户如何启用

**修复方案**:
- 在 `SettingsPage` 的环境变量列表中标注 `STRUCTFORGE_CONTENT_SAFETY_ENABLED` 为可选
- 或在 `SettingsPage` 添加内容安全开关 (简单的 toggle)

**影响**: 内容安全功能完全无法使用 (除非用户手动编辑 .env)

---

### 2.3 🟡 渲染进度在 ExportDialog 中不可见

**严重度**: 低 — 用户点击导出后看不到进度

**现状**:
- `ResultPage` 点击 RENDER ALL 后触发 `startRender` → `pollRenderJob`
- 但 TTS 进度已通过 `render_pipeline.py` 实时推送到 `render_jobs.warnings`
- 这些 warnings 在 `pollRenderJob` 中被接收但只用于 `console.error` 打印，**未展示给用户**
- `ExportDialog` 只显示百分比进度条，不显示阶段详情

**修复方案**:
- 在 `ExportDialog` 中添加一行 `warnings` 展示 (最近一条 warning)
- 或在 `VideoPlayer` 组件中展示渲染阶段

**影响**: 用户看到"正在渲染..."但不知道具体在做什么 (TTS? 分镜? 合成?)

---

### 2.4 🟡 封面图/高光片段 — Schema 就绪但无渲染

**严重度**: 低 — 后端生成但前端不展示

**现状**:
- v2 优化已将 `coverImagePath`/`highlightMoments` 添加到后端 schema 和前端 types
- Pydantic 校验不再阻断
- 但前端没有任何组件渲染这些数据
- `coverImagePath` 可用于 `HistoryPage` 项目卡片和 `VideoInfoCard`
- `highlightMoments` 可用于 `ResultPage` 时间线高亮标记

**修复方案**:
- `HistoryPage` 项目中展示 `coverImagePath` 缩略图 (替代当前的空灰色区域)
- `VideoInfoCard` 中展示封面图 (替代当前的占位)
- `ResultTimeline` 中高光时刻用 ⭐ 标记

**影响**: 用户看到更有信息量的 UI

---

## 三、⚡ 需优化的项 (6项)

### 3.1 ReviewPanel 组件提取

**现状**: `ReviewPanel` (Director's Cut 审核面板) 定义在 `ResultPage.tsx` L482-657 (~175行)，是该文件内最大的私有组件。

**优化**: 提取为 `src/components/result/ReviewPanel.tsx`
- 便于独立测试
- 减少 ResultPage.tsx 复杂度 (当前 ~700行)

---

### 3.2 快捷键提示改用 Modal

**现状**: `AppLayout.tsx:154` 用 `alert()` 弹出快捷键列表。

**优化**: 使用已有的 `Modal` 或 `Drawer` 组件 + `KeyboardShortcutHint` 组件
- 支持 `?` 键触发 (对标 Notion/Figma)
- 展示所有快捷键的格式化列表

---

### 3.3 MigratePage 7种风格折叠

**现状**: 7种脚本风格在底部固定条中作为 `<select>` 展示。这是当前用户需要做的最复杂选择。

**优化**: 
- 默认显示"智能建议" + "高级选项 ▼" 折叠按钮
- 折叠区展示其他 6 种风格
- 减少视觉噪音，降低选择焦虑

---

### 3.4 BGM 预置音轨

**现状**: `BGMEngine` 当 `bgm_library_dir` 未配置时调用 `generate_ambient()` 生成静默音频。用户体验差。

**优化**: 在 Docker 镜像或安装脚本中预置 2-3 首免版权背景音乐
- 从 Pixabay/Mixkit 获取 (CC0 许可)
- 放在 `ai-services/data/bgm/` 目录
- 默认 `bgm_library_dir` 指向该目录

---

### 3.5 渲染版本从4种简化为2种

**现状**: 4种渲染版本 (original/safe_fix/strong_hook/strong_conversion)
- `original` 和 `safe_fix` 仅在 `_segments_for_version` 中有微小差异 (safe_fix 过滤无素材分镜)
- 用户通常不理解这4种的区别

**优化**:
- 合并为 2 种: "标准渲染" (original) + "增强渲染" (strong_hook)
- 在 ExportDialog 中用中文描述差异

---

### 3.6 前端 SSE 实时进度替代轮询

(已在修复项 2.1 中描述)

---

## 四、✅ 保持不变

以下模块/功能经深度审查确认无误，无需变动：

**核心管道**: `AnalysisPipeline` → `MigratorService` → `VideoRenderPipeline` — 设计良好
**评分引擎**: `BurstMetricsCalculator` (41指标) + `BurstAuditor` (LLM审计) — 差异化竞争力
**缺口系统**: `GapDetector` + `GapFiller` (4策略) — 自动化完整
**结构编辑**: `StructureEditor` (undo/redo 持久化) — 实现正确
**素材匹配**: `AssetAnalyzer` + `AssetMatcher` (LLM匹配) — 覆盖完整
**NL编辑**: `NLEditorService` — 自然语言修改结构
**TTS引擎**: `TTSEngine` — Edge TTS + 火山双引擎 + 进度反馈
**ComfyUI**: `ComfyUIService` — RunningHub 集成 + 下载重试
**提示词引擎**: `prompt_engine/` — 模块化清晰，7文件活跃
**数据层**: `repository.py` + `schemas.py` — 完整CRUD+迁移
**路由**: 全部9个文件 — RESTful设计规范
**前端状态**: `store/index.ts` — 36 actions 覆盖完整
**UI组件**: 13个基础组件 — Swiss spa 主题统一
**页面**: 7页 — 全部功能完整
**mock**: `mockAnalysisResult.ts` — store dev模式使用

---

## 五、执行优先级

| 优先级 | 类别 | 项数 | 预计工时 |
|------|------|:--:|:--:|
| P0 | 🗑️ 删除 — 死代码清理 | 8 | 0.5h |
| P1 | 🔧 修复 — 功能断裂 | 4 | 4h |
| P2 | ⚡ 优化 — 体验提升 | 6 | 5h |

**总计**: ~9.5h

### 删除清单 (逐个确认)

```
□ ai-services/services/frame_renderer.py
□ src/components/migrate/GapPanel.tsx
□ src/components/migrate/GapPanel.test.tsx
□ src/mocks/projects.ts
□ src/mocks/gaps.ts
□ src/mocks/versions.ts
□ src/mocks/assets.ts
□ src/services/api.ts: 删除8个死方法 (L218-220, L257-258, L271-272, L273-274, L277-278, L289-301)
□ src/services/api.test.ts: 删除 migrateVariant 测试 (L114附近)
```

### 后端端点保留清单 (明确不删除)

```
✅ POST /api/v1/image/generate          — CLI/内部工具
✅ POST /api/v1/migrate/{id}/variant    — 未来多版本
✅ POST /api/v1/render/{id}/upgrade-to-video/ — WAN 2.2 roadmap
✅ GET  /api/v1/render/upgrade-status/  — 同上
✅ GET  /api/v1/templates               — 外部集成
✅ GET  /api/v1/pipelines               — 外部集成
✅ GET  /api/v1/analyze/{id}/stream     — SSE 优化待启用
✅ GET  /api/v1/render/{id}/stream      — SSE 优化待启用
✅ GET  /api/v1/audit/{id}/template     — 模板复用
```
