# AI 辅助工具使用说明

> 参赛作品: StructForge | 2026-06-10

---

## 使用的 AI 工具清单

| 工具 | 用途 | 使用环节 |
|------|------|------|
| **Doubao LLM** (豆包 Seed 2.0) | 视频结构提取、脚本迁移生成、Flux 提示词生成 | 分析层/迁移层 |
| **Doubao Vision** (豆包多模态) | 产品图片分析: 标签提取、颜色识别、OCR文本、品类推断 | 分析层 |
| **RunningHub ComfyUI** | Flux 文生图 (电商产品照)、WAN 2.2 图生视频 | 生成层 |
| **Edge TTS** (微软) | 免费语音合成, 为视频生成中文配音 | 生成层 |
| **Volcano ASR** (火山引擎) | 样例视频语音转写 | 分析层 |
| **FFmpeg** | 视频场景检测、关键帧提取、视频拼接、BGM混音、字幕烧录 | 分析层/生成层 |
| **Pillow** | 图片渲染, ComfyUI 不可用时的备用方案 | 生成层 |
| **Claude Code** (Anthropic) | 编码实现、代码审查、架构优化、Bug修复 | 开发全流程 |

---

## 自主设计与实现声明

以下核心能力由参赛者自主设计，**未**依赖现成产品直接生成:

### 1. 视频结构定义 (自创)

基于电商带货视频的特点，自主定义 **5段说服心理学框架**:
- Hook (开头吸引)、Pain (痛点放大)、Product (产品展示)、Proof (卖点证明)、CTA (转化号召)
- 每段包含 5 个制作参数维度: camera/emotion/pace/subtitle_anim/visual_fx
- 参数由 LLM 分析样例后自主分配, 非模板复制

### 2. 结构迁移引擎 (自创)

- 设计 LLM 迁移 Prompt (包含结构骨架 + 产品信息 + 节奏数据 + 健康度诊断)
- 脚本归一化后处理 (分镜类型强制覆盖、质量门控、回退模板)
- 5 篇分镜描述压缩为紧凑表格, 降低 Token 消耗

### 3. 素材缺口检测算法 (自创)

- 4 策略引擎: reorder/packaging/aigc/recompose
- 语义关键词扩展组 (厨房→灶台/料理台等 9 组)
- 缺口严重度分级 (Hook/CTA=critical, 其他=warning)

### 4. Flux 提示词生成器 (自创)

- 6 层专业提示词结构: 构图/主体/灯光/环境/动作/技术
- LLM 驱动生成, 包含具体光比(8:1)、镜头型号(Sony A7R V, 100mm macro)、材质描述
- 规则引擎降级链 (LLM失败→PromptEngine备用)

### 5. 7 步视频渲染管道 (自创)

- Template Method 模式: Prepare→TTS→Segments→Overlay→Assembly→BGM→Finalize
- 原视频分辨率自适应 (从分析结果读取, 不硬编码1080×1920)
- TTS 驱动时长 (Pixelle-Video 架构借鉴, 自主实现)

### 6. 前端设计系统 (自创)

- Swiss spa premium 风格: 暖白(#FAFAF9) + 金色(#C8843C) + 绿色(#4A9E7C)
- 67 组件统一设计, 响应式布局
- SSE 实时进度推送

---

## 竞品参考 (仅调研, 未使用代码)

- **Pixelle-Video**: 参考其 ComfyUI/RunningHub 集成模式和 Template Method 管道设计
- **剪映/CapCut**: 参考其视频创作交互形态
- **Runway**: 参考其 AI 视频生成的产品设计

所有核心代码为自主实现, 未复制竞品源码。
