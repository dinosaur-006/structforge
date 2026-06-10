# StructForge 爆款结构迁移引擎 — 完整产品深度分析报告 v2

> 生成日期：2026-06-10 | 分析范围：全代码库 ~105 源文件 (53 后端 + 52 前端) | 基于 P0-P3 优化后的代码库

---

## 一、产品概览

### 1.1 产品定位

StructForge 是一个 **AI 驱动的爆款视频结构迁移引擎**。核心功能：上传一条爆款样例视频 → AI 分析其结构 (hook/pain/product/proof/CTA) → 用户输入新产品信息 → AI 将爆款结构迁移到新产品上 → 生成 AI 画面 + TTS 配音 + 字幕的新视频。

### 1.2 技术栈

| 层 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 数据库 | SQLite + SQLAlchemy |
| AI/LLM | Doubao Seed (豆包) via OpenAI-compatible API |
| AI 图像 | ComfyUI RunningHub (Flux 文生图) + WAN 2.2 (图生视频) |
| AI 语音 | Edge TTS (免费) / 火山 TTS (API) |
| 视频处理 | FFmpeg + Pillow |
| 前端框架 | React 18 + TypeScript + Vite |
| 状态管理 | Zustand (persisted) |
| UI 样式 | Tailwind CSS (Swiss spa premium 主题) |
| 路由 | React Router v6 |

### 1.3 全流程闭环

```
上传样例视频 → AI分析结构 → 上传素材 → 缺口检测与补全
    → 输入产品信息 → 生成AI脚本 → 渲染视频 → 查看结果
```

---

## 二、后端全模块分析 (53 个 Python 文件)

### 2.1 核心入口层 (3 文件)

| 文件 | 行数 | 作用 | 状态 |
|------|:--:|------|:--:|
| `main.py` | 403 | FastAPI 应用工厂，注册所有路由、中间件、CORS、WebSocket、健康检查、全局异常处理 | ✅ |
| `config.py` | 78 | Pydantic Settings，37 个配置项 (LLM/ASR/Vision/AIGC/TTS/BGM/ComfyUI等) | ✅ |
| `seed.py` | ~60 | Demo 种子数据生成 | ✅ |

### 2.2 数据层 (2 文件)

| 文件 | 作用 | 状态 |
|------|------|:--:|
| `models/schemas.py` | 46+ Pydantic 模型 — `VideoMeta` 新增 `coverImagePath` 字段；`VideoStructure` 新增 `highlightMoments`/`shot_pool` 字段 | ✅ |
| `models/repository.py` | SQLiteRepository，6 张表，60+ 方法 (CRUD + 迁移 + 历史栈) | ✅ |

**数据库表**: `analysis_jobs` / `projects` / `assets` / `render_jobs` / `script_versions` (5 表)

### 2.3 路由层 (9 文件)

| 路由文件 | 前缀 | 端点 | 状态 |
|------|------|:--:|:--:|
| `routes/projects.py` | `/api/v1/projects` | 5 (CRUD) | ✅ |
| `routes/structure.py` | `/api/v1/structure/{project_id}` | 11 (CRUD+undo/redo+NL编辑) | ✅ |
| `routes/assets.py` | `/api/v1/assets` | 4 (上传/列表/匹配/缩略图) | ✅ |
| `routes/gaps.py` | `/api/v1/gaps` | 3 (检测/单个修复/全部修复) | ✅ |
| `routes/migrate.py` | `/api/v1/migrate` | 3 (生成/获取/变体/版本历史) | ✅ |
| `routes/render.py` | `/api/v1/render` | 5 (渲染/取消/查询/SSE流/视频升级) | ✅ |
| `routes/optimize.py` | `/api/v1/optimize` | 3 (波形/缩略图/蓝图) — POST端点已删除 | ✅ |
| `routes/audit_api.py` | `/api/v1/audit` | 2 (全模态审计/模板提取) | ✅ |
| `main.py` 内联 | `/api/v1/*` | 8 (capabilities/media/image/pipelines/templates/analyze/diagnostics/health) | ✅ |

**总 API 端点数: 44**

### 2.4 核心服务层 (51 个 .py 文件，含 prompt_engine 子包)

#### 2.4.1 主流程服务 (最核心 — 6 文件)

| 服务文件 | 行数 | LLM调用 | 作用 | 状态 |
|------|:--:|:--:|------|:--:|
| `pipeline.py` | 278 | ✅ Doubao Seed | 视频分析全流程 (场景检测→关键帧→ASR→视觉→结构提取) | ✅ |
| `migrator.py` | 1094 | ✅ Doubao Seed | 脚本生成 (结构→LLM迁移→评分预测→转场/贴纸) | ✅ |
| `render_pipeline.py` | 756 | ❌ | 视频渲染7步管道 — TTS进度实时反馈 + ComfyUI下载重试 | ✅ |
| `compositor.py` | 613 | ❌ | 渲染入口 (转发到 VideoRenderPipeline) — 旧代码已清除 | ✅ |
| `gap_detector.py` | 197 | ❌ | 4策略缺口检测 (reorder/packaging/aigc/recompose) | ✅ |
| `gap_filler.py` | 502 | ❌ | 缺口修复 (ComfyUI/Seedream/Pillow/reorder) | ✅ |

#### 2.4.2 AI 生成服务 (5 文件)

| 服务文件 | 核心功能 | 外部API | 状态 |
|------|------|:--:|:--:|
| `comfyui_service.py` | ComfyUI RunningHub 文生图+图生视频 | RunningHub API | ✅ |
| `ai_video_service.py` | Seedance/Kling/Runway 提示词构建 | ❌ 仅生成prompt | ✅ |
| `tts_engine.py` | Edge TTS + 火山 TTS 语音合成 | Edge TTS / 火山API | ✅ |
| `bgm_engine.py` | 背景音乐节拍检测+混音 | ❌ 本地librosa | ✅ |
| `cover_generator.py` | 封面图生成 (关键帧+文字叠加) | ❌ 本地Pillow | ✅ |

#### 2.4.3 分析与评分服务 (5 文件)

| 服务文件 | 核心功能 | LLM调用 | 状态 |
|------|------|:--:|:--:|
| `burst_metrics.py` | 41项指标爆款评分 (Hook/Trust/Density/Pacing/CTA/Retention) | ❌ 纯规则引擎 | ✅ |
| `burst_auditor.py` | 全模态审计 (规则+LLM双引擎) | ✅ Doubao Seed | ✅ |
| `result_evaluator.py` | 结果评估 (baseline/qualitative_review) | ✅ Doubao Seed | ✅ |
| `highlight_detector.py` | 高光片段检测 (情绪+视觉+ASR融合) | ✅ Doubao Seed | ✅ |
| `scene_classifier.py` | 场景类型分类 (hook/pain/product/proof/cta) | ✅ Doubao Vision | ✅ |

#### 2.4.4 编辑与优化服务 (5 文件)

| 服务文件 | 核心功能 | LLM调用 | 状态 |
|------|------|:--:|:--:|
| `structure_editor.py` | 结构编辑器 (CRUD+undo/redo历史栈) | ❌ | ✅ |
| `nl_editor.py` | 自然语言结构编辑 | ✅ Doubao Seed | ✅ |
| `auto_reorder.py` | AI 自动重排优化 (gap_filler 调用) | ❌ 确定性算法 | ✅ |
| `transition_advisor.py` | 转场推荐 | ✅ Doubao Seed | ✅ |
| `overlay_advisor.py` | 贴纸/强调元素推荐 | ❌ 关键词映射 | ✅ |

#### 2.4.5 素材处理服务 (5 文件)

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `asset_analyzer.py` | 素材上传+分析+场景分类 | ✅ |
| `asset_matcher.py` | 素材与分镜智能匹配 (LLM) | ✅ |
| `media.py` | 视频媒体处理 (场景检测/关键帧/探针) | ✅ |
| `asr.py` | 语音转写 (WhisperX/火山ASR) | ✅ |
| `vision.py` | 视觉分析 (关键帧→标签/OCR/品类) | ✅ |

#### 2.4.6 渲染与输出服务 (5 文件)

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `blueprint_renderer.py` | Pillow蓝图卡渲染+payload构建 | ✅ |
| `frame_renderer.py` | HTML→PNG 帧渲染 (备用方案，当前未被调用) | ⚠️ |
| `animated_overlay.py` | 动画叠加层 (Remotion/Pillow) | ✅ |
| `renderer_abstraction.py` | 渲染引擎抽象工厂 | ✅ |
| `template_util.py` | HTML模板工具 | ✅ |
| `pipeline_registry.py` | 渲染管道注册表 | ✅ |

#### 2.4.7 提示词引擎 (prompt_engine/ — 7 文件)

| 文件 | 作用 | 状态 |
|------|------|:--:|
| `engine.py` | 提示词引擎主入口 | ✅ |
| `assembler.py` | 提示词拼装器 | ✅ |
| `validator.py` | 提示词校验器 | ✅ |
| `vocabulary.py` | 品类词汇库 | ✅ |
| `negative_prompts.py` | 负向提示词 | ✅ |
| `adapters/seedance.py` | Seedance适配器 | ✅ |
| `adapters/runway.py` | Runway适配器 | ✅ |

> 注意：`adapters/kling.py` 已删除 (零引用死代码)

#### 2.4.8 基础设施服务 (10 文件)

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `llm_client.py` | LLM客户端 (RobustLLMClient+指数退避) | ✅ |
| `llm_structure.py` | LLM结构提取客户端 | ✅ |
| `llm_presets.py` | LLM预设配置 | ✅ |
| `structure_cache.py` | 结构缓存 (基于视频指纹) | ✅ |
| `content_safety.py` | 内容安全审查 (默认关闭) | ⚠️ |
| `auth.py` | API Key 中间件 (可选) | ⚠️ |
| `generation_notifier.py` | WebSocket 实时通知 | ✅ |
| `waveform.py` | 音频波形数据提取 | ✅ |
| `reference_assets.py` | 参考视频素材绑定 | ✅ |
| `path_utils.py` | 路径工具 | ✅ |
| `core.py` | 核心工具 | ✅ |
| `projects.py` | 项目服务 | ✅ |
| `uploads.py` | 上传服务 | ✅ |

> 已删除 8 个死代码文件：`remotion_client.py`、`optimization_pipeline.py`、`phase0_structure.py`、`phase1_multimodal.py`、`phase4_transitions.py`、`phase5_color.py`、`optimization_models.py`、`prompt_engine/adapters/kling.py`

---

## 三、前端全模块分析 (52 个 TS/TSX 文件)

### 3.1 路由与页面 (7 页)

| 页面 | 路由 | 核心功能 | 状态 |
|------|------|------|:--:|
| `ProjectListPage` | `/projects` | 项目列表、创建/删除 | ✅ |
| `AnalyzePage` | `/analyze` | 视频上传、分析进度、结构查看、**BurstAuditPanel** | ✅ |
| `MigratePage` | `/migrate/:projectId` | 创作简报、NL编辑、素材上传、**缺口摘要**、脚本生成 | ✅ |
| `ResultPage` | `/result/:projectId` | 视频播放、时间线、评分对比、导出、蓝图预览、**渲染错误恢复** | ✅ |
| `HistoryPage` | `/history` | 项目历史画廊 (筛选/搜索/骨架屏) — **已修复状态路由** | ✅ |
| `SettingsPage` | `/settings` | 服务状态、LLM Ping测试、环境变量参考 | ✅ |
| `NotFoundPage` | `*` | 404 | ✅ |

### 3.2 核心组件

#### 3.2.1 布局组件

| 组件 | 作用 | 状态 |
|------|------|:--:|
| `AppLayout` | 主布局 (侧边栏+内容区+FAQ+语言切换+快捷键帮助) | ✅ |
| `WorkflowSteps` | 4步进度条 (分析→编辑→生成→结果) — **步骤可点击导航** | ✅ |

#### 3.2.2 分析页组件 (12 个)

| 组件 | 作用 | 数据源 | 状态 |
|------|------|------|:--:|
| `VideoUploader` | 拖拽上传视频 | store.startAnalysis → API | ✅ |
| `AnalysisProgress` | 分析进度条+阶段 | store.progress/stage | ✅ |
| `VideoInfoCard` | 视频元信息卡片 | store.analysisResult.meta | ✅ |
| `PackagingStructure` | 包装结构展示 | store.analysisResult.packaging | ✅ |
| `ScriptStructure` | 脚本结构展示 | store.analysisResult.script | ✅ |
| `RhythmStructure` | 节奏结构展示 | store.analysisResult.rhythm | ✅ |
| `StructureTabs` | 多Tab结构切换 | store.analysisResult | ✅ |
| `BurstAuditPanel` | **爆款审计面板** | API `/audit/{jobId}` | ✅ |
| `HealthAssessment` | 健康度评估 | store.analysisResult.health | ✅ |
| `CapabilityStatusPanel` | AI能力状态 | API `/capabilities` | ✅ |
| `SampleComparison` | 多样例比较 | store.analysisSamples | ✅ |
| `MetricCard` | 指标卡片 | BurstAuditPanel 子组件 | ✅ |

#### 3.2.3 编辑页组件 (5 个)

| 组件 | 作用 | 数据源 | 状态 |
|------|------|------|:--:|
| `CreativeBriefPanel` | 创作简报编辑 | project.brief | ✅ |
| `AssetPanel` | 素材上传+列表 | store.assets | ✅ |
| `NLEditInput` | 自然语言编辑输入 | API nlEdit | ✅ |
| `SegmentDrawer` | 分镜详情编辑抽屉 | store.selectedSegmentId | ✅ |
| `SegmentBlock` | 分镜块 (时间线) | 子组件 | ✅ |

#### 3.2.4 结果页组件 (8 个)

| 组件 | 作用 | 数据源 | 状态 |
|------|------|------|:--:|
| `VideoPlayer` | 视频播放器 | store.outputUrl | ✅ |
| `ResultTimeline` | 分镜时间线 (含波形+字幕轨) | store.versions[].timeline | ✅ |
| `WaveformOverlay` | 音频波形Canvas渲染 | store.waveform | ✅ |
| `CompareRadar` | 雷达图对比 | store.versions[].health | ✅ |
| `ExportDialog` | 导出对话框 | store.isExporting | ✅ |
| `PayloadPreviewDrawer` | AI生成Payload预览 | store.blueprintPayloads | ✅ |
| `TimelineSpecPreview` | 时间线规范预览 | script.metadata.timelineSpec | ✅ |
| `AIReview` | AI定性评审 | script.metadata.ai_review | ✅ |
| `VersionTabs` | 版本切换Tab | store.versions | ✅ |

#### 3.2.5 共享组件 (3 个)

| 组件 | 作用 | 状态 |
|------|------|:--:|
| `LLMOutagePanel` | LLM服务中断面板 | ✅ |
| `FAQPanel` | FAQ面板 | ✅ |
| `ErrorBoundary` | 全局错误边界 | ✅ |

#### 3.2.6 UI 基础组件 (13 个)

Button, Badge, Modal, Drawer, Tabs, EmptyState, ErrorAlert, MetricRow, SourceLegend, SectionHeader, Skeleton, Toast, TopProgress, KeyboardShortcutHint, ConfirmDialog

### 3.3 状态管理 (Zustand)

**文件**: `src/store/index.ts` (775行)

**状态字段**: 37 个 | **Actions**: 36 个

| Action 类别 | Actions | 对应API |
|------|------|------|
| 项目管理 | fetchProjects, addProject, updateProjectBrief, removeProject | projects CRUD |
| 视频分析 | startAnalysis, fetchAnalysisSamples, selectReferenceSample | analyze endpoints |
| 结构编辑 | loadProjectStructure, updateSegment, reorderSegments, deleteSegment, undo, redo, reset, nlEdit | structure endpoints |
| 素材管理 | fetchAssets, uploadAsset | assets endpoints |
| 缺口管理 | fetchGaps, fixGap, fixAllGaps | gaps endpoints |
| 脚本生成 | migrateScript, loadFinalScript | migrate endpoints |
| 结果查看 | fetchResultVersions, setVersion | migrate versions endpoint |
| 视频渲染 | startRender, pollRenderJob | render endpoints |
| UI | toggleSidebar, addToast, removeToast, setRouteLoading, setLLMOutage, fetchCapabilities, fetchBlueprintPayloads | 无 |

---

## 四、前后端对齐分析

### 4.1 完全对齐的模块 ✅

| 功能 | 后端端点 | 前端调用 | 数据流通 |
|------|------|------|:--:|
| 项目CRUD | `routes/projects.py` 5端点 | `api.ts` 5方法 + store 5 actions | ✅ |
| 视频分析 | `main.py` `/analyze` + `/analyze/{job_id}` | `api.startAnalysis/getAnalysis` + store | ✅ |
| 分析样例 | `main.py` `/analyze/project/{id}/samples` | `api.listAnalysisSamples` + store | ✅ |
| 结构CRUD | `routes/structure.py` 11端点 | `api.ts` 11方法 + store | ✅ |
| 自然语言编辑 | `routes/structure.py` `/nl-edit` | `api.nlEditStructure` + store.nlEdit | ✅ |
| 素材管理 | `routes/assets.py` 4端点 | `api.ts` 4方法 + store | ✅ |
| 缺口检测修复 | `routes/gaps.py` 3端点 | `api.ts` 3方法 + store | ✅ |
| 脚本生成 | `routes/migrate.py` 3端点 | `api.ts` 3方法 + store | ✅ |
| 渲染 | `routes/render.py` 5端点 | `api.ts` 5方法 + store | ✅ |
| 爆款审计 | `routes/audit_api.py` 2端点 | `AnalyzePage` 直接fetch | ✅ |
| AI能力查询 | `main.py` `/capabilities` | `api.getCapabilities` + store + AnalyzePage + SettingsPage | ✅ |
| 波形 | `routes/optimize.py` `/waveform` | `api.getWaveform` + ResultPage | ✅ |
| 缩略图 | `routes/optimize.py` `/thumbnail` | `api.getThumbnail` + ResultTimeline | ✅ |
| 蓝图Payload | `routes/optimize.py` `/blueprint-payloads` | `api.getBlueprintPayloads` + store | ✅ |

### 4.2 后端端点无前端调用 ⚠️

| 端点 | 用途 | 状态 |
|------|------|:--:|
| `GET /api/v1/templates` | HTML模板列表 | `api.listTemplates()` 存在但无组件调用 |
| `GET /api/v1/pipelines` | 渲染管道列表 | `api.listPipelines()` 存在但无组件调用 |
| `POST /api/v1/image/generate` | 独立图片生成 | 仅后端内部使用 |
| `POST /api/v1/media/preview` | 媒体预览 | `api.previewMedia()` 存在但无组件调用 |
| `POST /api/v1/migrate/{id}/variant` | 脚本变体生成 | `api.migrateVariant()` 存在但仅测试文件引用 |

### 4.3 前端 API 方法无后端对应 ❌

| 前端方法 | 状态 |
|------|:--:|
| `api.runOptimization()` | ❌ 后端 POST `/optimize/{project_id}` 已删除。前端方法未删除，调用会返回 404 |

### 4.4 孤立前端组件 ⚠️

| 组件 | 状态 |
|------|:--:|
| `GapPanel.tsx` | 完整实现 (缺口列表+修复按钮)，但**未被任何页面渲染**。仅存在于测试文件中 |
| `GapPanel.test.tsx` | 测试文件孤立 |

### 4.5 数据字段全覆盖 ✅

| 数据字段 | 后端 | 前端 | 状态 |
|------|:--:|:--:|:--:|
| `VideoMeta.coverImagePath` | ✅ schemas.py | ✅ types.ts | ✅ |
| `VideoStructure.highlightMoments` | ✅ schemas.py | ✅ types.ts | ✅ |
| `VideoStructure.shot_pool` | ✅ schemas.py | ✅ types.ts | ✅ |
| `Capabilities.videoGeneration` | ✅ main.py | ✅ types.ts | ✅ |
| `FinalSegment.visual_requirements` | ✅ schemas.py | ✅ types.ts | ✅ |

---

## 五、服务模块实用度分析

### 5.1 活跃度分布

| 类别 | 文件数 | 高活跃 | 中活跃 | 低活跃/备用 |
|------|:--:|:--:|:--:|:--:|
| 核心服务 | 6 | 6 | 0 | 0 |
| AI生成 | 5 | 5 | 0 | 0 |
| 分析评分 | 5 | 5 | 0 | 0 |
| 编辑优化 | 5 | 5 | 0 | 0 |
| 素材处理 | 5 | 5 | 0 | 0 |
| 渲染输出 | 6 | 5 | 0 | 1 (`frame_renderer.py` 备用) |
| 提示词引擎 | 7 | 7 | 0 | 0 |
| 基础设施 | 12 | 10 | 2 (`content_safety.py` + `auth.py` 可选) | 0 |
| **总计** | **51** | **48** | **2** | **1** |

**代码活跃率: 94%** (比优化前的 86% 提升 8 个百分点)

---

## 六、多模式/用户选择点分析

### 6.1 当前用户需要做选择的地方

| 位置 | 选择项 | 选项数 | 影响 |
|------|------|:--:|------|
| MigratePage 底部 | 脚本风格 | **7** (智能建议/高点击/高转化/快节奏/高质感/小红书CES/视频号裂变) | LLM 生成策略 |
| ResultPage ExportDialog | 渲染版本 | **4** (original/safe_fix/strong_hook/strong_conversion) | 分镜选择逻辑 |
| ResultPage ExportDialog | 分辨率 | **2** (720p/1080p) | 输出分辨率 |
| ResultPage | 版本对比 | 2版本雷达图对比 | 查看评分差异 |
| AnalyzePage | 多样例选择 | N个分析样例中选参考 | 改变结构模板 |

### 6.2 已简化的模式

- ✅ `ResultPage` 的 `reviewMode` 已移除，ReviewPanel 始终显示
- ✅ `render_pipeline.py` 视觉生成已简化为 ComfyUI → Pillow 单路径
- ✅ TTS 驱动 duration 已固定 (不再回退到 LLM duration)
- ✅ `compositor.py` 已移除 `use_new_pipeline` 开关，始终使用 VideoRenderPipeline
- ✅ `routes/optimize.py` 已移除 POST 端点 (6相优化管道)，仅保留 3 个辅助端点
- ✅ 删除 8 个死代码文件 (~2000行)

### 6.3 仍可简化的模式 (建议)

1. **7种脚本风格** → 默认选择"智能建议"并折叠高级选项
2. **4种渲染版本** → `original` 和 `safe_fix` 差异微小，可合并为 2 种
3. **前端 API 方法** → `runOptimization()` 应删除 (后端端点已不存在)

---

## 七、全流程体验分析

### 7.1 完整用户旅程

```
[项目列表 /projects] → 点击"新建分析"
    ↓
[分析页 /analyze] → 拖拽上传样例视频 → 等待AI分析 (5-10分钟)
    ↓  展示: CapabilityStatus + VideoInfoCard + BurstAuditPanel + StructureTabs
    ↓
[编辑页 /migrate/:id] → 查看缺口摘要 (新增) → 填写创作简报
    ↓  → 可选: 上传产品素材
    ↓  → 可选: NL编辑
    ↓  → 选择风格 → 点击"生成视频脚本"
    ↓
[结果页 /result/:id] → 查看 Review Panel (Director's Cut)
    ↓  → 点击 RENDER ALL → 等待渲染 (3-8分钟) → TTS进度实时推送 (新增)
    ↓  → 观看生成的视频 + 时间线 + 评分雷达图 + 评分预测卡片 + 渲染质量卡片
    ↓  → 导出 JSON/SRT/视频
    ↓  → 渲染失败后刷新页面可恢复错误信息 (新增)

[历史页 /history] → 项目画廊 → 按状态正确路由 (修复)
[设置页 /settings] → 服务状态 + LLM Ping + 环境变量参考
```

### 7.2 流程中的断点/痛点

| 痛点 | 位置 | 严重度 | 说明 |
|------|------|:--:|------|
| 分析耗时长 | AnalyzePage | 中 | 5-10分钟轮询 (有 SSE 端点但前端未启用) |
| GapPanel 未渲染 | MigratePage | 低 | 组件存在但页面未引入；已添加缺口摘要作为替代 |
| 渲染失败难排查 | ResultPage | **已修复** | sessionStorage 持久化 + 页面恢复 |
| runOptimization 死方法 | api.ts | 低 | 后端端点已删除但前端方法残留 |
| 封面图不展示 | 多处 | 低 | 后端 schema 已支持，前端类型已添加，但无渲染组件 |
| 高光片段不展示 | ResultPage | 低 | 后端 schema 已支持，前端类型已添加，但无渲染组件 |

### 7.3 数据流完整性

| 数据链路 | 状态 |
|------|:--:|
| 上传视频 → 场景检测 → 关键帧 → LLM结构提取 → VideoStructure | ✅ |
| VideoStructure → 缺口检测 → 4策略评估 → MaterialGap[] | ✅ |
| MaterialGap[] → 缺口修复 → 更新VideoStructure + Asset[] | ✅ |
| VideoStructure + ProductBrief → LLM迁移 → FinalScript | ✅ |
| FinalScript → BurstMetrics → predicted_scores + baseline_scores | ✅ |
| FinalScript → ResultEvaluator → ai_review | ✅ |
| FinalScript → VideoRenderPipeline → output.mp4 + self_audit | ✅ |
| 41项指标 → BurstAuditPanel (AnalyzePage 展示) | ✅ |
| predicted_scores/baseline_scores → ResultPage 评分卡片 | ✅ |
| self_audit → ResultPage 渲染质量卡片 | ✅ |
| ai_review → AIReview 组件 | ✅ |
| 波形数据 → WaveformOverlay | ✅ |
| 蓝图Payload → PayloadPreviewDrawer | ✅ |
| 封面图 → ⚠️ schema就绪但前端无渲染 | ⚠️ |
| 高光片段 → ⚠️ schema就绪但前端无渲染 | ⚠️ |
| 贴纸推荐 → ⚠️ metadata存储但前端未渲染 | ⚠️ |
| 视频升级 (WAN 2.2) → ⚠️ 后端端点存在但前端无触发 | ⚠️ |
| TTS 进度 → ✅ 实时推送到 render job warnings | ✅ |

---

## 八、架构质量评估

### 8.1 优点

1. **清晰的 Template Method 模式**: `VideoRenderPipeline` 7步管道设计，每步独立可测试
2. **TTS 驱动 duration**: 音频先生成，视频后适配 — 正确的架构决策
3. **线程安全**: `new_event_loop()` 模式解决 ComfyUI 异步调用问题
4. **评分系统完善**: 41项指标覆盖6个维度，规则引擎+LLM双引擎
5. **前端设计统一**: Tailwind CSS 变量实现全局主题一致 (Swiss spa premium)
6. **API 契约清晰**: Pydantic StrictModel 确保数据结构一致
7. **历史栈完整**: undo/redo 正确持久化到 SQLite
8. **错误处理分层**: LLM outage 面板 → toast → 重试 → sessionStorage 恢复
9. **死代码清理**: 8个文件删除 + compositor 精简，代码活跃率 94%
10. **ComfyUI 下载重试**: 3次指数退避，提升 AI 图片生成可靠性

### 8.2 待改进

1. **前端残留**: `api.runOptimization()` 方法仍在，后端端点已不存在
2. **GapPanel 孤立**: 完整实现的组件未被任何页面使用
3. **数据展示缺口**: 封面图/高光片段/贴纸推荐后端已生成，前端未渲染
4. **frame_renderer.py 备用**: Playwright HTML→PNG 方案未被调用
5. **SSE 未启用**: 后端有 SSE 端点但前端仍用轮询

### 8.3 文件统计

| 指标 | 优化前 | 优化后 | 变化 |
|------|:--:|:--:|:--:|
| 后端 Python 文件 | 67 | 53 | -14 (-21%) |
| 前端 TS/TSX 文件 | 46 | 52 | +6 (测试文件) |
| 总 API 端点 | 45+ | 44 | -1 |
| API 方法 (前端) | 30 | 30 | — |
| 代码活跃率 | 86% | 94% | +8% |
| 死代码行数 | ~2000 | ~200 | -90% |

---

## 九、总结

StructForge 已完成从"可用 MVP"到"精简对齐产品"的升级。核心闭环 (Project→Analyze→Migrate→Result) 前后端完全对齐。P0-P3 修复和优化已实施，8 个死代码文件已清除，代码活跃率从 86% 提升至 94%。

**可直接使用**: 全流程闭环、AI分析、脚本生成、视频渲染、评分系统、时间线、导出、历史页、设置页

**存在小问题**: 前端残留 `runOptimization()` 方法、GapPanel 孤立组件、封面图/高光片段前端未渲染

**已删除**: remotion_client / optimization_pipeline (6相) / phase0-5 / kling 适配器 / compositor 旧渲染路径
