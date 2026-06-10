# StructForge — 电商爆款视频结构迁移引擎

> 课题: 爆款结构迁移引擎 | 赛道: 剪辑类/营销类
>
> 提交时间: 2026-06 | GitHub: https://github.com/dinosaur-006/structforge

---

## 一、产品概述

StructForge 是一个专注于**电商带货短视频**的 AI 创作平台。它不复制爆款视频的内容，而是**迁移其创作方法**——将验证过的说服心理学结构骨架应用到全新商品上，生成可直接投放的短视频。

### 核心工作流

```
上传样例视频 → AI提取5段结构 → 输入新产品信息 → AI生成脚本 → AI画面+TTS配音 → 成片
```

### 电商场景适配

| 设计 | 说明 |
|------|------|
| 5段叙事结构 | Hook→Pain→Product→Proof→CTA 带货标准框架 |
| 产品图视觉分析 | Vision AI 提取颜色/纹理/标签 → 注入提示词 |
| ComfyUI 云生图 | RunningHub GPU 生成电商产品照，无需自建集群 |
| LLM 提示词工程 | 6层专业结构，包含光比/镜头/材质参数 |
| 逐段生图/生视频 | 关键分镜可选 WAN 2.2 视频，普通分镜用 Flux 图片 |

### 赛题任务完成清单

| 任务 | 要求 | 实现 |
|------|------|:--:|
| 任务1 | 样例输入与解析 | ✅ 拖拽上传 + 多条样例 + ASR/Vision分析 |
| 任务2 | 结构拆解(≥2类) | ✅ 3类: 脚本/节奏/包装 + LLM健康度 |
| 任务3 | 新内容与素材输入 | ✅ 产品名/卖点/产品图 + 缺口识别 |
| 任务4 | 结构迁移生成(≥2项) | ✅ 脚本+分镜+时间线+成片 (4项) |
| 任务5 | 素材缺口识别 | ✅ 4策略检测引擎 |
| 任务6 | 素材缺口补全 | ✅ AIGC(ComfyUI)+包装补全+结构重排 |
| 任务7 | 迁移过程可视化 | ✅ StructureTabs+ReviewPanel+Gap展示 |
| 任务8 | 结果可验证 | ✅ 视频Demo+分镜时间线+结构对比 |
| 任务9 | 画面包装(≥2项) | ✅ 字幕样式+卖点卡片生成 |
| 任务10 | 多版本生成 | ✅ 标准/高转化/高质感 3版 |
| 任务11 | 真实素材适配 | ✅ 场景分类+产品图识别+匹配推荐 |
| 任务12 | 人工可调 | ✅ 参数编辑+NL编辑+风格选择 |
| 任务13 | 自然语言编辑 | ✅ "把开头改得更抓人" 一句话修改 |

---

## 二、整体 AI 架构

```
┌─────────────────────────────────────────────────────────┐
│                     StructForge AI 架构                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  输入层                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 样例视频  │  │ 产品图片  │  │ 商品信息  │              │
│  │ (MP4)    │  │ (JPG/PNG)│  │ (文本)    │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │             │                     │
│  分析层  FFmpeg场景检测 + 火山ASR转写 + 豆包Vision分析      │
│       │              │             │                     │
│  理解层  ┌────────────▼─────────────┐                    │
│          │   Doubao LLM 结构提取     │                    │
│          │ 脚本+节奏+包装+6维健康度  │                    │
│          └────────────┬─────────────┘                    │
│                       │                                  │
│  迁移层  ┌────────────▼─────────────┐                    │
│          │   Doubao LLM 脚本迁移     │                    │
│          │  GapDetector 4策略检测    │                    │
│          │  LLM FluxPromptGenerator  │                    │
│          └────────────┬─────────────┘                    │
│                       │                                  │
│  生成层  ┌────────────▼─────────────┐                    │
│          │  RunningHub ComfyUI       │                    │
│          │   Flux 文生图 (1080p)     │                    │
│          │   WAN 2.2 图生视频 (512p) │                    │
│          │  Edge TTS 语音合成         │                    │
│          │  FFmpeg 视频合成+TTS+BGM   │                    │
│          └────────────┬─────────────┘                    │
│                       │                                  │
│  输出层  新视频 MP4 (AI画面+TTS配音+ASS字幕)               │
└─────────────────────────────────────────────────────────┘
```

---

## 三、自主设计能力说明

### 3.1 视频"结构"定义 (自创)

电商视频结构 = **5段说服心理学框架** × **5维制作参数**

每段结构由 LLM 分析样例后自主分配，非模板复制:

```
Hook(3s) → Pain(5s) → Product(8s) → Proof(5s) → CTA(4s)
 快推       缓推         缓推          横移         快推
 弹入       淡入         缩放          逐字         缩放
 快         正常         正常          正常         快
 惊讶       亲切         兴奋          权威         紧迫
 震屏       无           放大          慢动作       放大
```

### 3.2 结构迁移方法 (自创)

```
原视频结构: Hook(快节奏冲突词) → Pain(场景共鸣) → CTA(限时紧迫)
                              ↓ LLM迁移
新脚本:     Hook(快推+震屏+惊讶) "你绝对没吃过的趣多多新口味!"
           Pain(缓推+亲切)     "每次吃完零食都觉得太甜..."
           CTA(快推+紧迫)      "现在拍一单到手30包!"
```

LLM Prompt 包含: 原视频结构骨架 + 产品信息 + 镜头节奏数据 + 健康度诊断

### 3.3 素材缺口检测算法 (自创)

```
用户素材 vs 5个结构槽位 → 4策略引擎:
  reorder: 调整段落顺序降低缺失依赖
  packaging: 生成标题卡/卖点卡补位
  aigc:     ComfyUI Flux 生成AI画面 (实际渲染使用)
  recompose: 从用户视频中裁切复用

语义关键词扩展组: 厨房→灶台/料理台, 美妆→膏体/面部, 数码→材质/内部拆解...
```

### 3.4 LLM 驱动 Flux 提示词生成器 (自创)

6层专业电商摄影提示词结构:

```
1. COMPOSITION: 9:16 vertical medium close-up, centered framing
2. SUBJECT: 具体产品 + 颜色(#D2691E) + 材质(glossy/metallic)
3. LIGHTING: 8:1 ratio, 45° key light, rim light, fill light
4. ENVIRONMENT: seamless pure white background
5. ACTION: slow rotating on turntable, crumbs flying
6. TECHNICAL: Sony A7R V, 100mm f/2.8 macro, 8k, hyperrealistic
```

LLM 优先 → 规则引擎降级 (零中断)

### 3.5 7步视频渲染管道 (自创)

Template Method 模式: Prepare → TTS(预生成音频) → 逐段处理 → 动画叠加 → 视频拼接 → BGM混音 → 自审计

- 原视频分辨率自适应 (960×544 → 960×544, 1080×1920 → 1080×1920)
- TTS 驱动时长 (先合成配音, 再按音频时长调整画面)
- Pixelle-Video 架构借鉴, 独立实现

### 3.6 前端设计系统 (自创)

Swiss spa premium 美学: 暖白(#FAFAF9) + 金色(#C8843C) + 绿色(#4A9E7C)
67组件统一圆角(border-xl) + 柔和边框(border/60) + 极浅阴影(shadow-sm)

---

## 四、技术栈

| 层 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Vite + Tailwind CSS + Zustand |
| **后端** | Python 3.12+ + FastAPI + Pydantic + SQLAlchemy |
| **LLM** | Doubao Seed 2.0 (OpenAI-compatible API) |
| **视觉** | Doubao Vision API (产品图标签/颜色/OCR) |
| **ASR** | Volcano BigModel ASR v3 (语音转写) |
| **图像** | RunningHub ComfyUI Flux (text-to-image) |
| **视频** | RunningHub WAN 2.2 (image-to-video) |
| **语音** | Edge TTS (免费) |
| **视频处理** | FFmpeg (场景检测/关键帧/合成) |
| **数据库** | SQLite (嵌入式, 零配置) |

---

## 五、AI工具使用声明

| 工具 | 用途 | 环节 |
|------|------|------|
| Doubao LLM | 视频结构提取、脚本迁移、Flux提示词 | 理解/迁移 |
| Doubao Vision | 产品图标签/颜色/OCR/品类分析 | 分析 |
| Volcano ASR | 样例视频语音转写 | 分析 |
| RunningHub ComfyUI | Flux文生图 + WAN2.2图生视频 | 生成 |
| Edge TTS | 中文配音语音合成 | 生成 |
| FFmpeg | 场景检测/关键帧/视频合成/BGM混音 | 分析/生成 |
| Pillow | 蓝图卡渲染 (降级备用) | 生成 |
| Claude Code | 编码实现、架构优化、代码审查 | 开发 |

**竞品参考(仅调研, 未复制源码)**: Pixelle-Video (ComfyUI集成模式)、剪映 (视频创作交互形态)

**自主设计部分**: 结构定义(5段框架+5维参数)、结构迁移方法(LLM prompt工程)、缺口检测算法(4策略引擎)、FluxPromptGenerator(6层提示词)、7步渲染管道、Swiss spa设计系统、前后端全栈架构。

---

## 六、安全边界

1. API Key 仅存储在服务端 `.env` 文件，前端不可见
2. 可选 `ContentSafetyService` 关键词拦截 LLM 脚本内容
3. 文件上传限制 500MB + MIME 白名单检查
4. 所有数据本地 SQLite 存储, 不上传至第三方
5. 可选 `X-API-Key` 中间件保护后端 API

---

## 七、本地部署

```bash
git clone https://github.com/dinosaur-006/structforge.git
cd structforge

# 后端
cd ai-services
copy .env.example .env          # 编辑填入API Key
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端 (新终端)
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`

**必需的 API Key**: Doubao LLM + RunningHub ComfyUI (2个)

---

## 八、项目结构

```
structforge/
├── ai-services/          # Python 后端 (FastAPI)
│   ├── main.py           # 应用入口 + 路由注册
│   ├── config.py         # Pydantic Settings
│   ├── models/           # Pydantic + SQLAlchemy
│   ├── routes/           # 9个 API 路由
│   ├── services/         # 50+ 核心服务模块
│   │   ├── pipeline.py           # 视频分析(多模态)
│   │   ├── migrator.py           # 脚本迁移(LLM)
│   │   ├── render_pipeline.py    # 7步视频渲染
│   │   ├── flux_prompt_generator.py  # LLM提示词
│   │   ├── gap_detector.py       # 缺口检测(4策略)
│   │   ├── gap_filler.py         # 缺口修复
│   │   ├── comfyui_service.py    # ComfyUI集成
│   │   ├── asr.py                # 火山ASR转写
│   │   └── prompt_engine/        # 提示词引擎
│   └── tasks/            # 异步任务
├── src/                  # React 前端 (TypeScript)
│   ├── pages/            # 7页面 (分析/编辑/结果/项目/历史/设置/404)
│   ├── components/       # 40+ 组件
│   ├── store/            # Zustand 状态管理
│   ├── services/         # API 客户端
│   └── shared/           # 类型/工具
├── docs/                 # 项目文档
└── data/                 # 运行时数据 (SQLite + outputs)
```
