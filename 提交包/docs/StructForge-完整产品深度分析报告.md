# StructForge 爆款结构迁移引擎 — 完整产品深度分析报告

> 生成日期：2026-06-10 | 分析范围：全代码库 113 个源文件 (67 后端 + 46 前端)

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

## 二、后端全模块分析 (67 个 Python 文件)

### 2.1 核心入口层 (3 文件)

| 文件 | 作用 | 状态 |
|------|------|:--:|
| `main.py` | FastAPI 应用工厂，注册所有路由、中间件、CORS、WebSocket、健康检查、全局异常处理 | ✅ 活跃 |
| `config.py` | Pydantic Settings，37 个配置项 (LLM/ASR/Vision/AIGC/TTS/BGM/ComfyUI等) | ✅ 活跃 |
| `seed.py` | Demo 种子数据生成 | ✅ 活跃 |

### 2.2 数据层 (2 文件)

| 文件 | 作用 | 状态 |
|------|------|:--:|
| `models/schemas.py` | 46 个 Pydantic 模型 (VideoStructure/FinalScript/GapStrategy/BlueprintPayload等) | ✅ 活跃 |
| `models/repository.py` | SQLiteRepository，6 张表，60+ 方法 (CRUD + 迁移 + 历史栈) | ✅ 活跃 |

**数据库表结构**:
- `analysis_jobs` — 视频分析任务 (含 _vision_frames/_asr_data 隐藏字段)
- `projects` — 项目 (含 current_structure/undo_stack/redo_stack/script_json)
- `assets` — 用户上传素材
- `render_jobs` — 渲染任务
- `script_versions` — 脚本版本历史
- (隐式) `script_versions` — 联合主键 (project_id, version)

### 2.3 路由层 (9 文件)

| 路由文件 | 前缀 | 端点数量 | 状态 |
|------|------|:--:|:--:|
| `routes/projects.py` | `/api/v1/projects` | 5 (CRUD + List) | ✅ |
| `routes/structure.py` | `/api/v1/structure/{project_id}` | 11 (CRUD + undo/redo + NL编辑) | ✅ |
| `routes/assets.py` | `/api/v1/assets` | 4 (上传/列表/匹配/缩略图) | ✅ |
| `routes/gaps.py` | `/api/v1/gaps` | 3 (检测/单个修复/全部修复) | ✅ |
| `routes/migrate.py` | `/api/v1/migrate` | 3 (生成/获取/变体/版本历史) | ✅ |
| `routes/render.py` | `/api/v1/render` | 5 (渲染/取消/查询/SSE流/视频升级) | ✅ |
| `routes/optimize.py` | `/api/v1/optimize` | 4 (6相管道/波形/缩略图/蓝图) | ✅ |
| `routes/audit_api.py` | `/api/v1/audit` | 2 (全模态审计/模板提取) | ✅ |
| `main.py` 内联路由 | `/api/v1/*` | 8 (capabilities/media/image/pipelines/templates/analyze/diagnostics/health) | ✅ |

**总 API 端点数: 45+**

### 2.4 核心服务层 (50+ 文件)

#### 2.4.1 主流程服务 (最核心)

| 服务文件 | 核心类/函数 | LLM调用 | 作用 | 状态 |
|------|------|:--:|------|:--:|
| `pipeline.py` | `AnalysisPipeline.run()` | ✅ Doubao Seed | 视频分析全流程 (场景检测→关键帧→ASR→视觉→结构提取) | ✅ |
| `migrator.py` | `MigratorService.generate()` | ✅ Doubao Seed | 脚本生成 (结构→LLM迁移→评分预测→转场/贴纸) | ✅ |
| `render_pipeline.py` | `VideoRenderPipeline.run()` | ❌ | 视频渲染7步管道 (TTS→分镜→动画→组装→BGM) | ✅ |
| `compositor.py` | `Compositor.render()` | ❌ | 旧渲染器 (保留向后兼容) | ⚠️ 被新管道取代 |
| `gap_detector.py` | `GapDetector.detect()` | ❌ | 4策略缺口检测 (reorder/packaging/aigc/recompose) | ✅ |
| `gap_filler.py` | `GapFiller.fix()/fix_all()` | ❌ | 缺口修复 (ComfyUI/Pillow/reorder) | ✅ |

#### 2.4.2 AI 生成服务

| 服务文件 | 核心功能 | 外部API | 状态 |
|------|------|:--:|:--:|
| `comfyui_service.py` | ComfyUI RunningHub 文生图+图生视频 | RunningHub API | ✅ |
| `ai_video_service.py` | Seedance/Kling/Runway 提示词构建 | ❌ 仅生成prompt | ✅ |
| `tts_engine.py` | Edge TTS + 火山 TTS 语音合成 | Edge TTS / 火山API | ✅ |
| `bgm_engine.py` | 背景音乐节拍检测+混音 | ❌ 本地librosa | ✅ |
| `cover_generator.py` | 封面图生成 (关键帧+文字叠加) | ❌ 本地Pillow | ✅ |

#### 2.4.3 分析与评分服务

| 服务文件 | 核心功能 | LLM调用 | 状态 |
|------|------|:--:|:--:|
| `burst_metrics.py` | 41项指标爆款评分 (Hook/Trust/Density/Pacing/CTA/Retention) | ❌ 纯规则引擎 | ✅ |
| `burst_auditor.py` | 全模态审计 (规则+LLM双引擎) | ✅ Doubao Seed | ✅ |
| `result_evaluator.py` | 结果评估 (baseline/qualitative_review) | ✅ Doubao Seed | ✅ |
| `highlight_detector.py` | 高光片段检测 (情绪+视觉+ASR融合) | ✅ Doubao Seed | ✅ |
| `scene_classifier.py` | 场景类型分类 (hook/pain/product/proof/cta) | ✅ Doubao Vision | ✅ |

#### 2.4.4 编辑与优化服务

| 服务文件 | 核心功能 | LLM调用 | 状态 |
|------|------|:--:|:--:|
| `structure_editor.py` | 结构编辑器 (CRUD+undo/redo历史栈) | ❌ | ✅ |
| `nl_editor.py` | 自然语言结构编辑 | ✅ Doubao Seed | ✅ |
| `auto_reorder.py` | AI 自动重排优化 | ❌ 确定性算法 | ⚠️ 可能未集成 |
| `transition_advisor.py` | 转场推荐 | ✅ Doubao Seed | ✅ |
| `overlay_advisor.py` | 贴纸/强调元素推荐 | ❌ 关键词映射 | ✅ |

#### 2.4.5 素材处理服务

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `asset_analyzer.py` | 素材上传+分析+场景分类 | ✅ |
| `asset_matcher.py` | 素材与分镜智能匹配 (LLM) | ✅ |
| `media.py` | 视频媒体处理 (场景检测/关键帧/探针) | ✅ |
| `asr.py` | 语音转写 (WhisperX/火山ASR) | ✅ |
| `vision.py` | 视觉分析 (关键帧→标签/OCR/品类) | ✅ |

#### 2.4.6 渲染与输出服务

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `blueprint_renderer.py` | Pillow蓝图卡渲染+payload构建 | ✅ |
| `frame_renderer.py` | HTML→PNG 帧渲染 | ⚠️ 可能被取代 |
| `animated_overlay.py` | 动画叠加层 (Remotion/Pillow) | ✅ |
| `renderer_abstraction.py` | 渲染引擎抽象工厂 | ✅ |
| `template_util.py` | HTML模板工具 | ✅ |
| `pipeline_registry.py` | 渲染管道注册表 | ✅ |

#### 2.4.7 提示词引擎 (prompt_engine/)

| 文件 | 作用 | 状态 |
|------|------|:--:|
| `engine.py` | 提示词引擎主入口 | ✅ |
| `assembler.py` | 提示词拼装器 | ✅ |
| `validator.py` | 提示词校验器 | ✅ |
| `vocabulary.py` | 品类词汇库 | ✅ |
| `negative_prompts.py` | 负向提示词 | ✅ |
| `adapters/seedance.py` | Seedance适配器 | ✅ |
| `adapters/runway.py` | Runway适配器 | ✅ |
| `adapters/kling.py` | Kling适配器 | ⚠️ 引用较少 |

#### 2.4.8 基础设施服务

| 服务文件 | 核心功能 | 状态 |
|------|------|:--:|
| `llm_client.py` | LLM客户端 (RobustLLMClient+指数退避) | ✅ |
| `llm_structure.py` | LLM结构提取客户端 | ✅ |
| `llm_presets.py` | LLM预设配置 | ✅ |
| `structure_cache.py` | 结构缓存 (基于视频指纹) | ✅ |
| `content_safety.py` | 内容安全审查 | ⚠️ 默认关闭 |
| `auth.py` | API Key 中间件 | ⚠️ 可选 |
| `generation_notifier.py` | WebSocket 实时通知 | ✅ |
| `waveform.py` | 音频波形数据提取 | ✅ |
| `reference_assets.py` | 参考视频素材绑定 | ✅ |
| `optimization_pipeline.py` | 6相优化管道 | ⚠️ 与主流程平行 |
| `optimization_models.py` | 优化模型定义 | ⚠️ 仅optimize路由使用 |

---

## 三、前端全模块分析 (46 个 TS/TSX 文件)

### 3.1 路由与页面 (7 页)

| 页面 | 路由 | 核心功能 | 状态 |
|------|------|------|:--:|
| `ProjectListPage` | `/projects` | 项目列表、创建/删除 | ✅ |
| `AnalyzePage` | `/analyze` | 视频上传、分析进度、结构查看 | ✅ |
| `MigratePage` | `/migrate/:projectId` | 创作简报、NL编辑、素材上传、脚本生成 | ✅ |
| `ResultPage` | `/result/:projectId` | 视频播放、时间线、评分对比、导出、蓝图预览 | ✅ |
| `HistoryPage` | `/history` | 历史记录 | ⚠️ 空白页 |
| `SettingsPage` | `/settings` | 设置 | ⚠️ 空白页 |
| `NotFoundPage` | `*` | 404 | ✅ |

### 3.2 核心组件 (40+ 组件)

#### 3.2.1 布局组件

| 组件 | 作用 | 状态 |
|------|------|:--:|
| `AppLayout` | 主布局 (侧边栏+内容区) | ✅ |
| `WorkflowSteps` | 4步进度条 (分析→编辑→生成→结果) | ✅ |

#### 3.2.2 分析页组件

| 组件 | 作用 | 数据源 | 状态 |
|------|------|------|:--:|
| `VideoUploader` | 拖拽上传视频 | store.startAnalysis → API | ✅ |
| `AnalysisProgress` | 分析进度条+阶段 | store.progress/stage | ✅ |
| `VideoInfoCard` | 视频元信息卡片 | store.analysisResult.meta | ✅ |
| `PackagingStructure` | 包装结构展示 | store.analysisResult.packaging | ✅ |
| `ScriptStructure` | 脚本结构展示 | store.analysisResult.script | ✅ |
| `RhythmStructure` | 节奏结构展示 | store.analysisResult.rhythm | ✅ |
| `StructureTabs` | 多Tab结构切换 | store.analysisResult | ✅ |
| `BurstAuditPanel` | 爆款审计面板 | API `/audit/{jobId}` | ✅ |
| `HealthAssessment` | 健康度评估 | store.analysisResult.health | ✅ |
| `CapabilityStatusPanel` | AI能力状态 | API `/capabilities` | ✅ |
| `SampleComparison` | 多样例比较 | store.analysisSamples | ✅ |
| `MetricCard` | 指标卡片 | BurstAuditPanel 子组件 | ✅ |

#### 3.2.3 编辑页组件

| 组件 | 作用 | 数据源 | 状态 |
|------|------|------|:--:|
| `CreativeBriefPanel` | 创作简报编辑 | project.brief | ✅ |
| `AssetPanel` | 素材上传+列表 | store.assets | ✅ |
| `NLEditInput` | 自然语言编辑输入 | API nlEdit | ✅ |
| `SegmentDrawer` | 分镜详情编辑抽屉 | store.selectedSegmentId | ✅ |
| `SegmentBlock` | 分镜块 (时间线) | 子组件 | ✅ |
| `GapPanel` | 缺口列表+修复 | store.gaps | ⚠️ 在MigratePage中未渲染 |

#### 3.2.4 结果页组件

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

#### 3.2.5 共享组件

| 组件 | 作用 | 状态 |
|------|------|:--:|
| `LLMOutagePanel` | LLM服务中断面板 | ✅ |
| `FAQPanel` | FAQ面板 | ✅ |
| `ErrorBoundary` | 全局错误边界 | ✅ |

#### 3.2.6 UI 基础组件 (13 个)

Button, Badge, Modal, Drawer, Tabs, EmptyState, ErrorAlert, MetricRow, SourceLegend, SectionHeader, Skeleton, Toast, TopProgress, KeyboardShortcutHint, ConfirmDialog

### 3.3 状态管理 (Zustand)

**文件**: `src/store/index.ts` (775行)

**状态字段**: 37个
**Actions**: 36个

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
| UI | toggleSidebar, addToast, removeToast, setRouteLoading | 无 |

---

## 四、前后端对齐分析

### 4.1 完全对齐的模块 ✅

| 功能 | 后端端点 | 前端调用 | 数据流通 |
|------|------|------|:--:|
| 项目CRUD | `routes/projects.py` 5端点 | `api.ts` 5方法 + store 5 actions | ✅ 畅通 |
| 视频分析 | `main.py` `/analyze` + `/analyze/{job_id}` | `api.startAnalysis/getAnalysis` + store | ✅ 畅通 |
| 分析样例 | `main.py` `/analyze/project/{id}/samples` | `api.listAnalysisSamples` + store | ✅ 畅通 |
| 结构CRUD | `routes/structure.py` 11端点 | `api.ts` 11方法 + store | ✅ 畅通 |
| 自然语言编辑 | `routes/structure.py` `/nl-edit` | `api.nlEditStructure` + store.nlEdit | ✅ 畅通 |
| 素材管理 | `routes/assets.py` 4端点 | `api.ts` 4方法 + store | ✅ 畅通 |
| 缺口检测修复 | `routes/gaps.py` 3端点 | `api.ts` 3方法 + store | ✅ 畅通 |
| 脚本生成 | `routes/migrate.py` 3端点 | `api.ts` 3方法 + store | ✅ 畅通 |
| 渲染 | `routes/render.py` 5端点 | `api.ts` 5方法 + store | ✅ 畅通 |
| AI能力查询 | `main.py` `/capabilities` | `api.getCapabilities` + store | ✅ 畅通 |
| 诊断 | `main.py` `/diagnostics/llm` | 无直接调用 (仅开发用) | ✅ |
| 审计 | `routes/audit_api.py` 2端点 | `BurstAuditPanel` 直接fetch | ✅ 畅通 |
| 波形 | `routes/optimize.py` `/waveform` | `api.getWaveform` + ResultPage useEffect | ✅ 畅通 |
| 缩略图 | `routes/optimize.py` `/thumbnail` | `api.getThumbnail` + ResultTimeline | ✅ 畅通 |
| 蓝图Payload | `routes/optimize.py` `/blueprint-payloads` | `api.getBlueprintPayloads` + store | ✅ 畅通 |
| 媒体预览 | `main.py` `/media/preview` | `api.previewMedia` | ✅ |
| 图片生成 | `main.py` `/image/generate` | 无直接调用 (后端内部使用) | ⚠️ 仅CLI测试 |
| 模板/Pipeline列表 | `main.py` `/templates` `/pipelines` | `api.listTemplates/listPipelines` | ⚠️ 前端未显示使用 |

### 4.2 后端有但前端未调用的端点 ⚠️

| 端点 | 用途 | 前端状态 |
|------|------|:--:|
| `GET /api/v1/templates` | HTML模板列表 | `api.listTemplates()` 存在但无组件调用 |
| `GET /api/v1/pipelines` | 渲染管道列表 | `api.listPipelines()` 存在但无组件调用 |
| `POST /api/v1/image/generate` | 独立图片生成 | 仅后端内部使用 |
| `POST /api/v1/migrate/{id}/variant` | 脚本变体生成 | `api.migrateVariant()` 存在但无UI触发 |

### 4.3 后端产生但前端未消费的数据字段 ⚠️

| 数据字段 | 来源 | 前端状态 |
|------|------|:--:|
| `VideoStructure.meta.shot_pool` | pipeline.py (场景池) | 前端types.ts 未定义 |
| `VideoStructure.meta.highlightMoments` | pipeline.py (高光检测) | 前端types.ts 未定义 |
| `VideoStructure.meta.coverImagePath` | pipeline.py (封面生成) | 前端types.ts 未定义 |
| `FinalScript.metadata.overlay_recommendations` | migrator.py (贴纸推荐) | 前端未渲染 |
| `FinalScript.metadata.migration_strategy` | migrator.py (迁移策略) | 前端AIReview可能展示 |
| `FinalScript.segments[].visual_requirements` | schemas.py | 前端types.ts 未定义 |
| `CapabilityStatusOut.videoGeneration` | main.py `/capabilities` | 前端Capabilities接口未包含 |

### 4.4 前端期望但后端未产出的数据 ⚠️

| 前端字段 | 期望来源 | 后端状态 |
|------|------|:--:|
| `Project.thumbnail` | types.ts | ❌ 后端ProjectOut无此字段 |
| `API Capabilities.videoGeneration` | api.ts → types.ts | ❌ types.ts Capabilities接口缺少此字段 |

### 4.5 孤立/空白页面 ⚠️

| 页面 | 路由 | 内容 | 问题 |
|------|------|------|------|
| `HistoryPage` | `/history` | 空白 | 侧边栏有入口，但页面只有标题没有实现 |
| `SettingsPage` | `/settings` | 空白 | 侧边栏有入口，但页面只有标题没有实现 |

---

## 五、服务模块实用度分析

### 5.1 高实用度模块 (核心流程必需) ✅

1. **AnalysisPipeline** — 视频分析入口，无可替代
2. **MigratorService** — 脚本生成，核心价值
3. **VideoRenderPipeline** — 视频渲染，最终输出
4. **BurstMetricsCalculator** — 41项评分，差异化竞争力
5. **TTSEngine** — TTS配音，视频完整性必需
6. **ComfyUIService** — AI图像生成，核心AI能力
7. **GapDetector + GapFiller** — 缺口检测修复
8. **StructureEditor** — 结构编辑+历史栈
9. **AssetAnalyzer + AssetMatcher** — 素材分析匹配

### 5.2 中等实用度模块 (增强体验) ⚡

1. **BGMEngine** — BGM混音 (已集成)
2. **TransitionAdvisor** — 转场推荐 (已集成)
3. **OverlayAdvisor** — 贴纸推荐 (已集成)
4. **CoverGenerator** — 封面生成 (后端生成但前端未展示)
5. **HighlightDetector** — 高光检测 (后端生成但前端未展示)
6. **NLEditorService** — NL编辑 (已集成)
7. **ContentSafetyService** — 内容安全 (默认关闭)
8. **StructureCache** — 结构缓存 (已集成)

### 5.3 低实用度/可能死代码模块 ❌

1. **OptimizationPipeline (6相)** — 与主流程平行的另一套优化管道，通过 `/optimize` 路由暴露，前端有 `api.runOptimization()` 但无任何UI触发。占用 6 个服务文件。
2. **prompt_engine/adapters/kling.py** — Kling适配器，引用极少
3. **remotion_client.py** — Remotion客户端，被 `renderer_abstraction.py` 抽象层包裹但很少直接使用
4. **frame_renderer.py** — HTML→PNG渲染，已被 `blueprint_renderer.py` 替代
5. **Compositor (旧)** — 被 `VideoRenderPipeline` 替代，`compositor.py` (~621行) 保留用于向后兼容
6. **auto_reorder.py** — AI自动重排，代码存在但未确认是否集成到gap_filler

### 5.4 文件冗余度统计

| 类别 | 文件数 | 活跃 | 半活跃 | 可能死代码 |
|------|:--:|:--:|:--:|:--:|
| 核心服务 | 15 | 13 | 2 | 0 |
| AI生成服务 | 5 | 5 | 0 | 0 |
| 分析评分 | 5 | 5 | 0 | 0 |
| 编辑优化 | 5 | 3 | 1 | 1 |
| 素材处理 | 5 | 5 | 0 | 0 |
| 渲染输出 | 5 | 4 | 1 | 0 |
| 提示词引擎 | 8 | 7 | 1 | 0 |
| 基础设施 | 11 | 9 | 1 | 1 |
| **总计** | **59** | **51** | **6** | **2** |

---

## 六、多模式/用户选择点分析

### 6.1 当前用户需要做选择的地方

| 位置 | 选择项 | 选项数 | 影响 |
|------|------|:--:|------|
| MigratePage 底部 | 脚本风格 | 7 (智能建议/高点击/高转化/快节奏/高质感/小红书CES/视频号裂变) | 传给LLM影响脚本生成策略 |
| ResultPage ExportDialog | 渲染版本 | 4 (original/safe_fix/strong_hook/strong_conversion) | 影响视频分镜选择逻辑 |
| ResultPage ExportDialog | 分辨率 | 2 (720p/1080p) | 视频输出分辨率 |
| ResultPage | 版本对比 | 2版本雷达图对比 | 查看不同版本评分差异 |
| AnalyzePage | 多样例选择 | N个分析样例中选参考 | 改变结构模板 |

### 6.2 已简化的模式

根据之前用户要求"单一流程不要多模式"：

- ✅ `ResultPage` 的 `reviewMode` 已移除，ReviewPanel 始终显示
- ✅ `render_pipeline.py` 的视觉生成已简化为 ComfyUI → Pillow 单一路径
- ✅ TTS 驱动 duration 已固定 (不再回退到 LLM duration)

### 6.3 仍可进一步简化的模式

1. **7种脚本风格** — 可以默认"智能建议"并隐藏高级选项
2. **4种渲染版本** — `original` 和 `safe_fix` 区别微小，可合并
3. **素材上传可选** — 不上传素材走全AI生成路径是合理的
4. **ComfyUI vs Pillow** — 后端自动选择 (有ComfyUI就用，没有就Pillow)，用户无需关心

---

## 七、全流程体验分析

### 7.1 完整用户旅程

```
[项目列表] → 点击"新建分析"
    ↓
[分析页] → 拖拽上传样例视频 → 等待AI分析 (5-10分钟)
    ↓  展示: VideoInfoCard + ScriptStructure + RhythmStructure + HealthAssessment
    ↓
[编辑页] → 填写创作简报 (产品名/卖点/受众/调性)
    ↓  → 可选: 上传产品素材 (图片/视频)
    ↓  → 可选: NL编辑 ("把Hook改得更震撼")
    ↓  → 选择风格 → 点击"生成视频脚本"
    ↓
[结果页] → 查看 Review Panel (所有分镜的AI提示词)
    ↓  → 点击 RENDER ALL → 等待渲染 (3-8分钟)
    ↓  → 观看生成的视频 + 时间线 + 评分雷达图
    ↓  → 导出 JSON/SRT/视频文件
```

### 7.2 流程中的断点/痛点

| 痛点 | 位置 | 严重度 | 说明 |
|------|------|:--:|------|
| 分析耗时长 | AnalyzePage | 中 | 5-10分钟无中间反馈 (可考虑SSE实时推送) |
| GapPanel未渲染 | MigratePage | 低 | GapPanel组件存在于代码但MigratePage未引入 |
| HistoryPage空白 | /history | 高 | 侧边栏有入口但完全不工作 |
| SettingsPage空白 | /settings | 高 | 侧边栏有入口但完全不工作 |
| 渲染失败难排查 | ResultPage | 中 | 错误信息显示在toast中，刷新即丢失 |
| 封面图不展示 | 多处 | 低 | 后端生成coverImagePath但前端未消费 |
| 高光片段不展示 | ResultPage | 低 | 后端检测highlightMoments但前端无组件 |

### 7.3 数据流完整性验证

| 数据链路 | 状态 |
|------|:--:|
| 上传视频 → 场景检测 → 关键帧 → LLM结构提取 → VideoStructure | ✅ |
| VideoStructure → 缺口检测 → 4策略评估 → MaterialGap[] | ✅ |
| MaterialGap[] → 缺口修复 → 更新VideoStructure + Asset[] | ✅ |
| VideoStructure + ProductBrief → LLM迁移 → FinalScript | ✅ |
| FinalScript → BurstMetrics → predicted_scores + baseline_scores | ✅ |
| FinalScript → ResultEvaluator → ai_review | ✅ |
| FinalScript → VideoRenderPipeline → output.mp4 + self_audit | ✅ |
| 41项指标 → BurstAuditPanel (前端展示) | ✅ |
| predicted_scores/baseline_scores → ResultPage评分卡片 | ✅ |
| self_audit → ResultPage渲染质量卡片 | ✅ |
| ai_review → AIReview组件 | ✅ |
| 波形数据 → WaveformOverlay | ✅ |
| 蓝图Payload → PayloadPreviewDrawer | ✅ |
| 封面图 → ❌ 前端未消费 | ❌ |
| 高光片段 → ❌ 前端未消费 | ❌ |
| 贴纸推荐 → ❌ 前端未消费 | ❌ |
| 素材缩略图 → AssetPanel (基础实现) | ⚠️ |
| 视频升级 (WAN 2.2) → ❌ 前端未触发 | ❌ |

---

## 八、架构质量评估

### 8.1 优点

1. **清晰的Template Method模式**: `VideoRenderPipeline` 的7步管道设计借鉴Pixelle-Video，每步独立可测试
2. **TTS驱动duration**: 音频先生成，视频后适配 — 正确的架构决策
3. **线程安全设计**: `new_event_loop()` 模式解决了ComfyUI异步调用在同步上下文中的问题
4. **评分系统完善**: 41项指标覆盖6个维度，规则引擎+LLM双引擎
5. **前端设计统一**: Tailwind CSS变量实现全局主题一致
6. **API契约清晰**: Pydantic StrictModel确保前后端数据结构一致
7. **历史栈完整**: undo/redo在结构编辑中正确持久化
8. **错误处理分层**: LLM outage面板 → toast通知 → 重试逻辑

### 8.2 待改进

1. **多套并行管道**: OptimizationPipeline与主流程平行运行，造成代码冗余
2. **空白页面**: HistoryPage和SettingsPage存在但未实现
3. **数据断链**: 封面图/高光片段/贴纸推荐后端生成但前端未展示
4. **旧代码残留**: compositor.py 621行被新管道取代但保留
5. **Kling适配器**: prompt_engine中Kling适配器几乎未使用
6. **API字段缺失**: 前端Capabilities接口缺少videoGeneration字段

### 8.3 文件统计

| 指标 | 数值 |
|------|:--:|
| 后端Python文件 | 67 |
| 前端TS/TSX文件 | 46 |
| 总API端点 | 45+ |
| Pydantic模型 | 46 |
| SQLite表 | 6 |
| Zustand state字段 | 37 |
| Zustand actions | 36 |
| API方法 (前端) | 30 |
| 评分指标数 | 41 |
| 配置项 | 37 |
| 脚本风格数 | 7 |
| 渲染版本数 | 4 |

---

## 九、总结

StructForge 已实现完整的 **视频分析→结构迁移→AI脚本生成→视频渲染** 闭环。核心流程 (Project→Analyze→Migrate→Result) 前后端完全对齐，45+个API端点与30个前端API方法一一对应。

**当前产品状态**: MVP+ (超越MVP但仍有一些边缘功能未完成)

**可直接使用**: 全流程闭环、AI分析、脚本生成、视频渲染、评分系统、时间线、导出

**需要补全**: HistoryPage、SettingsPage、封面图展示、高光片段展示、视频升级UI

**存在冗余**: OptimizationPipeline (6相)、compositor.py (旧渲染器)、Kling适配器

**代码健康度**: 约 86% 的代码处于活跃使用状态，约 14% 为半活跃或可能死代码。
