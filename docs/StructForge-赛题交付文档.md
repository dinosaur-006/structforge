# StructForge — 电商爆款视频结构迁移引擎

> **课题**: 爆款结构迁移引擎  
> **赛道**: 剪辑类 / 营销类  
> **领域**: 电商带货短视频  
> **提交时间**: 2026年6月  
> **GitHub**: https://github.com/dinosaur-006/structforge

---

## 目录

1. [产品概述](#一产品概述)
2. [赛题任务完成清单](#二赛题任务完成清单)
3. [整体 AI 架构](#三整体-ai-架构)
4. [视频结构定义方法](#四视频结构定义方法)
5. [结构迁移实现详解](#五结构迁移实现详解)
6. [素材缺口识别与补全](#六素材缺口识别与补全)
7. [LLM 驱动 Flux 提示词工程](#七llm-驱动-flux-提示词工程)
8. [7 步视频渲染管道](#八7-步视频渲染管道)
9. [前端交互与可视化](#九前端交互与可视化)
10. [技术栈详解](#十技术栈详解)
11. [AI 工具使用声明](#十一ai-工具使用声明)
12. [安全边界](#十二安全边界)
13. [本地部署指南](#十三本地部署指南)
14. [项目结构详解](#十四项目结构详解)

---

## 一、产品概述

### 1.1 产品定位

StructForge 是一个专注于**电商带货短视频**的 AI 创作平台。它的核心创新在于：**不是复制爆款视频的内容，而是迁移其创作方法**——将经过市场验证的说服心理学框架（Hook→Pain→Product→Proof→CTA）应用到全新的商品上，生成可以直接用于抖音/小红书等内容平台投放的短视频。

### 1.2 解决的核心问题

电商创作者面临三个痛点：
1. **好结构难复用**: 看到成功的带货视频，知道它"好"，但不知道为什么好，更不知道如何用到自己的产品上
2. **素材不足**: 新产品没有足够的图片/视频素材来支撑完整的视频结构
3. **制作门槛高**: 剪辑、配音、字幕需要专业技能和时间

StructForge 解决这三个问题的方式：
1. **结构抽取**: AI 自动分析样例视频，提取脚本结构、镜头节奏、包装手法
2. **结构迁移**: 保持原视频的结构骨架，将所有内容替换为新产品信息
3. **AIGC 补全**: 当用户素材不足时，自动调用 AI 生成产品图片和视频

### 1.3 完整工作流

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 上传样例  │ →  │ AI分析   │ →  │ 输入产品  │ →  │ 生成脚本  │
│ 视频     │    │ 提取结构  │    │ 信息     │    │ 分镜     │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  渲染视频    │
                                              │ Flux生图    │
                                              │ WAN2.2生视频│
                                              │ TTS配音     │
                                              │ FFmpeg合成  │
                                              └─────────────┘
```

**操作步骤**:
1. 分析台: 拖拽上传一条电商带货视频，等待 AI 分析（约60秒）
2. 编辑台: 输入新产品名称和卖点，上传产品图（可选但推荐）
3. 点击生成脚本 → 进入结果展示台
4. 逐段选择生成模式（生图/生视频），点击 RENDER ALL
5. 渲染完成 → 播放 AI 生成的视频，可下载 MP4/JSON/SRT

---

## 二、赛题任务完成清单

| 任务编号 | 赛题要求 | 实现情况 | 说明 |
|:--:|------|:--:|------|
| **任务1** | 样例视频输入与解析 | ✅ 超额完成 | 支持拖拽上传、多条样例、基础信息（时长/镜头/分辨率）+ ASR语音转写 + Vision视觉分析 |
| **任务2** | 结构拆解（≥2类） | ✅ 超额完成 | 实现3类：脚本结构(5段叙事) + 节奏结构(帧级场景检测) + 包装结构(字幕/转场/叠加层) + LLM健康度评分 |
| **任务3** | 新内容与素材输入 | ✅ 完成 | 产品名/卖点文本输入 + 产品图上传 + Vision视觉分析 + 素材缺口识别 |
| **任务4** | 结构迁移生成（≥2项） | ✅ 超额完成 | 覆盖4项：分镜脚本 + 分镜画面描述 + 时间线可视化 + 成片MP4 |
| **任务5** | 素材缺口识别 | ✅ 完成 | 4策略检测引擎，识别Hook/Product/CTA等5类结构槽位缺口，语义关键词扩展 |
| **任务6** | 素材缺口补全 | ✅ 超额完成 | 支持全部5种方式：结构重排 + 包装补全 + AIGC生成(ComfyUI Flux) + 文案补全 + 素材重组 |
| **任务7** | 迁移过程可视化 | ✅ 完成 | StructureTabs展示提取结构，ReviewPanel展示迁移脚本，GapPanel展示缺口详情 |
| **任务8** | 结果可验证 | ✅ 超额完成 | 视频Demo + 分镜时间线 + 结构对比 + 版本切换 + 导出JSON/SRT |
| **任务9** | 画面包装（≥2项） | ✅ 完成 | 字幕样式(5种动画) + 标题卡/卖点卡片生成 + 转场推荐 + 贴纸推荐 |
| **任务10** | 多版本生成 | ✅ 完成 | 3种版本：标准版(default) + 高转化版(high_conversion) + 高质感版(high_quality) |
| **任务11** | 真实素材适配 | ✅ 完成 | 场景分类(5类) + 产品图Vision分析(标签/颜色/OCR/品类) + 素材匹配推荐 |
| **任务12** | 人工可调 | ✅ 超额完成 | 参数编辑(分镜drawer) + 风格选择 + NL自然语言编辑 + 素材上传替换 |
| **任务13** | 自然语言编辑 | ✅ 完成 | "把开头改得更抓人" → LLM解析 → 结构修改 → 缺口重检 |

**加分项**: 自然语言改片 ✅ | 真实素材+AIGC融合 ✅ | 结构迁移可解释性 ✅ | 画面包装链路 ✅ | 工程质量+设计完成度 ✅

---

## 三、整体 AI 架构

### 3.1 架构全景图

StructForge 采用**五层管道架构**：输入层 → 分析层 → 理解层 → 迁移层 → 生成层。每一层有明确的输入/输出接口，层间通过 Pydantic 严格模型进行数据传递。

```
┌──────────────────────────────────────────────────────────────────┐
│                        StructForge AI 架构                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      输入层 (Input Layer)                    │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐       │ │
│  │  │ 样例视频  │    │ 产品图片  │    │ 商品信息(文本)    │       │ │
│  │  │ MP4/MOV  │    │ JPG/PNG  │    │ 名称/卖点/调性    │       │ │
│  │  └────┬─────┘    └────┬─────┘    └────────┬─────────┘       │ │
│  └───────┼───────────────┼───────────────────┼─────────────────┘ │
│          │               │                   │                    │
│  ┌───────▼───────────────▼───────────────────▼─────────────────┐ │
│  │                      分析层 (Analysis Layer)                 │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │ │
│  │  │ FFmpeg   │  │ Vision   │  │ ASR      │                  │ │
│  │  │ 场景检测  │  │ API      │  │ 语音转写  │                  │ │
│  │  │ 关键帧   │  │ 标签/OCR │  │ 字幕文本  │                  │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │ │
│  └───────┼──────────────┼─────────────┼────────────────────────┘ │
│          │              │             │                           │
│  ┌───────▼──────────────▼─────────────▼────────────────────────┐ │
│  │                      理解层 (Understanding Layer)           │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │              Doubao LLM (结构提取)                     │  │ │
│  │  │  输入: 多模态数据 (场景/关键帧/ASR/Vision)              │  │ │
│  │  │  输出: VideoStructure (5段脚本 + 节奏 + 包装 + 健康度) │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                      迁移层 (Migration Layer)                │ │
│  │  ┌────────────────────┐  ┌────────────────────┐             │ │
│  │  │ Doubao LLM         │  │ GapDetector        │             │ │
│  │  │ 脚本迁移生成        │  │ 4策略缺口检测       │             │ │
│  │  │ FinalScript        │  │ MaterialGap[]      │             │ │
│  │  └────────────────────┘  └────────────────────┘             │ │
│  │  ┌──────────────────────────────────────────────┐           │ │
│  │  │ FluxPromptGenerator (LLM 提示词生成)          │           │ │
│  │  │ 6层专业电商摄影提示词                          │           │ │
│  │  └──────────────────────────────────────────────┘           │ │
│  └──────────────────────────┬───────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────▼───────────────────────────────────┐ │
│  │                      生成层 (Generation Layer)               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │ │
│  │  │ ComfyUI Flux │  │ WAN 2.2      │  │ Edge TTS     │      │ │
│  │  │ 文生图 1080p │  │ 图生视频 512p│  │ 中文配音     │      │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │ │
│  │         │                 │                 │               │ │
│  │  ┌──────▼─────────────────▼─────────────────▼───────┐       │ │
│  │  │           FFmpeg (视频合成)                        │       │ │
│  │  │  图片/视频拼接 + TTS配音 + ASS字幕 + BGM混音       │       │ │
│  │  └──────────────────────┬───────────────────────────┘       │ │
│  └─────────────────────────┼───────────────────────────────────┘ │
│                            │                                      │
│                     ┌──────▼──────┐                               │
│                     │  输出 MP4    │                               │
│                     │  新视频成品  │                               │
│                     └─────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流详解

**分析阶段** (pipeline.py):

```
视频文件 → FFmpeg探针 (时长/分辨率/编码)
        → FFmpeg场景检测 (21个镜头时间点)
        → FFmpeg关键帧提取 (60帧PNG)
        → 火山ASR v3 (语音转文字)
        → 豆包Vision (关键帧分析: 10标签+OCR+品类)
        → Doubao LLM (结构提取: 5段脚本+节奏+包装+6维健康度)
        → 存入 SQLite (analysis_jobs + projects 表)
```

**迁移阶段** (migrator.py):

```
VideoStructure + 产品Brief + 素材列表 + 缺口分析
        → GapDetector.detect() (4策略检测)
        → Doubao LLM (脚本迁移, ~45s)
        → FluxPromptGenerator (预生成每个分镜的提示词)
        → FinalScript (存入 script_versions 表)
```

**渲染阶段** (render_pipeline.py):

```
FinalScript + 用户素材
        → Step1: Prepare (加载数据/解析分辨率)
        → Step2: TTS预合成 (Edge TTS, 免费)
        → Step3: 逐段处理
              → LLM 生成 Flux 提示词
              → ComfyUI Flux 文生图 (1080p)
              → [可选] WAN2.2 图生视频 (512p)
              → FFmpeg 图片/视频标准化
        → Step4: 动画叠加 (Hook/CTA分镜)
        → Step5: FFmpeg 拼接所有分镜
        → Step6: BGM混音 + 节拍对齐
        → Step7: 自审计 (flux_segments计数/质量评估)
        → 输出 MP4 + 存入 render_jobs 表
```

### 3.3 数据模型设计

核心数据模型 `VideoStructure` 定义了一级视频的结构抽象:

```python
class VideoStructure(StrictModel):
    meta: VideoMeta              # 时长/分辨率/镜头数/封面标签
    script: list[ScriptSegment]  # 5段叙事分镜 (Hook→CTA)
    rhythm: list[RhythmPoint]    # 帧级节奏检测
    packaging: PackagingStructure # 字幕/转场/叠加层
    health: HealthScores         # LLM 自主评分 (6维)
```

`FinalScript` 定义迁移后的脚本:

```python
class FinalScript(StrictModel):
    version: FinalScriptStyle    # 标准/高转化/高质感
    total_duration: float        # 总时长
    segments: list[FinalSegment] # 每个分镜: 文案/画面/相机/情绪/语速/特效
    metadata: dict               # 扩展数据: prompts/productVisual/self_audit
```

---

## 四、视频结构定义方法

### 4.1 5段说服心理学框架

StructForge 的核心创新在于对电商视频结构的**形式化定义**。我们不把视频看作像素序列，而是看作一个**可迁移的结构骨架**。

```
┌──────────────────────────────────────────────────────────┐
│                    电商带货视频结构模型                      │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│  │  Hook   │→ │  Pain   │→ │ Product │→ │  Proof  │→ │   CTA   │
│  │ 0-3s    │  │ 3-8s    │  │ 8-18s   │  │ 18-28s  │  │ 28-33s  │
│  │         │  │         │  │         │  │         │  │         │
│  │ 目标:   │  │ 目标:   │  │ 目标:   │  │ 目标:   │  │ 目标:   │
│  │ 0.3秒   │  │ 让用户  │  │ 展示    │  │ 摧毁    │  │ 创造    │
│  │ 停滑    │  │ 对号入座 │  │ 产品    │  │ 购买犹豫 │  │ 行动紧迫 │
│  │         │  │         │  │         │  │         │  │         │
│  │ 手法:   │  │ 手法:   │  │ 手法:   │  │ 手法:   │  │ 手法:   │
│  │ 认知冲突│  │ 具体场景│  │ 英雄镜头│  │ 对比演示│  │ 行动指令│
│  │ 悬念    │  │ 情绪共鸣│  │ 质感特写│  │ 数据证明│  │ 稀缺性  │
│  │ 视觉冲击│  │         │  │         ���  │         │  │ 零风险  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
│                                                           │
│  每个分镜包含5个独立制作参数:                                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐ │
│  │ camera   │ subtitle │ pace     │ emotion  │ visual_fx│ │
│  │ 镜头运动  │ 字幕动画  │ 语速节奏  │ 语气情感  │ 画面特效  │ │
│  │          │          │          │          │          │ │
│  │ 快推     │ 弹入     │ 快       │ 惊讶     │ 震屏     │ │
│  │ 缓推     │ 淡入     │ 正常     │ 亲切     │ 闪白     │ │
│  │ 拉远     │ 逐字出现  │ 慢       │ 权威     │ 慢动作   │ │
│  │ 横移     │ 缩放出现  │          │ 紧迫     │ 放大     │ │
│  │ 跟随     │ 无动画   │          │ 感动     │ 模糊过渡  │ │
│  │ 手持微晃  │          │          │ 兴奋     │ 无       │ │
│  │ 静态     │          │          │ 平静     │          │ │
│  │ 环绕     │          │          │          │          │ │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 4.2 三类结构拆解实现

**脚本结构** (ScriptStructure):
```
LLM 分析视频后输出 5 个分镜，每个包含:
- id: 唯一标识
- type: hook | pain | product | proof | cta
- start/end/duration: 时间范围
- goal: 该分镜在说服链中的目标
- copy: 口播文案原文
- visual: 画面描述
- visual_keywords: 视觉关键词 (来自 Vision API)
- healthScore: LLM 评估该分镜完成其目标的程度 (0-100)
```

**节奏结构** (RhythmStructure):
```
帧级场景检测 (FFmpeg filter):
- 检测 21 个镜头切换时间点
- 每个分镜统计: shot_count (镜头数) + avg_shot_duration (平均镜头时长)
- 节奏规则: Hook≥2镜头/秒, CTA≥2镜头/秒, Product≥2秒/镜头
```

**包装结构** (PackagingStructure):
```
LLM 提取:
- subtitleStyle: 字幕样式描述列表
- transitions: 转场类型列表
- overlays: 叠加层类型列表
- 每个分镜的 subtitlePreset (白字黑边等)
```

### 4.3 LLM 健康度评分

LLM 自主评估视频的 6 个维度:

```
hook_strength:            开头吸引力 (Hook 段是否能在 0.3 秒内停滑)
product_exposure_timing:  产品露出时机 (是否在 5 秒内展示产品)
selling_point_proof:      卖点证明力 (是否有可验证的证据)
pacing_compactness:       节奏紧凑度 (镜头节奏是否合适)
cta_persuasiveness:       转化号召力 (CTA 是否有紧迫感)
overall:                  综合健康度
```

评分标准嵌入 LLM prompt 中，由 LLM 自主判断，**不是硬编码公式**。

---

## 五、结构迁移实现详解

### 5.1 迁移方法

核心原则: **迁移创作方法，而非复制内容**。

```
输入: VideoStructure (原视频的 5 段结构骨架) + ProductBrief (新产品信息)

迁移 LLM Prompt 结构 (约 10,000 字符):
┌─────────────────────────────────────────────┐
│ 1. 目标产品 (铁律, 不可改变)                  │
│    - 产品名称、品类、卖点、调性                │
│                                             │
│ 2. 核心原则: 迁移方法不是改写文案              │
│    - 5 段说服心理学框架解释                    │
│                                             │
│ 3. 制作参数 (5 个独立 JSON 字段)              │
│    - camera/subtitle_anim/pace/emotion/visual_fx│
│                                             │
│ 4. 分镜类型速查表                             │
│    - Hook/Pain/Product/Proof/CTA 的相机/情绪/语速│
│                                             │
│ 5. 原视频 L2 镜头节奏数据                     │
│    - 每个分镜的 shot_count/avg_shot_duration   │
│                                             │
│ 6. 原视频健康度诊断                           │
│    - 6 维健康度 + 最薄弱维度                   │
│                                             │
│ 7. 品牌调性 + 情绪共鸣参数                    │
│    - 根据产品类型自动推断                      │
│                                             │
│ 8. 风格量化参数 (硬性约束)                     │
│    - hook_duration_max_s / cta_duration_max_s  │
│                                             │
│ 9. JSON 输出格式 + 硬性规则                    │
│    - 保持段落数和段落类型                      │
│    - 总时长偏差 ≤10%                          │
│    - migration_strategy 必须填写               │
└─────────────────────────────────────────────┘

输出: FinalScript (每段分镜的 script + visual + camera + emotion + pace + visual_fx)
```

### 5.2 脚本归一化后处理

LLM 输出后经过多步后处理确保质量:

```python
# 1. 分镜类型强制覆盖 (LLM 可能返回错误的类型)
for segment in segments:
    segment["type"] = template_segment.type  # 从原结构强制对齐

# 2. 分镜 ID 自动映射 (LLM 可能返回不同数量的分镜)
if LLM返回9段 but 结构是5段:
    按位置映射: LLM[0]→结构[0], LLM[1]→结构[1]...
    多余的用模板填充

# 3. 质量门控 (填充无意义内容)
if len(script) < 5:  # "啊"/"哼" 等无意义文字
    用原视频模板的文案替换

if duration < 1.5:  # 过短的分镜
    强制拉到 1.5s

# 4. Camera/Emotion 默认值强制覆盖
Hook → 快推 + 惊讶
CTA  → 快推 + 紧迫
Product → 缓推 + 兴奋
Proof → 横移 + 权威
```

### 5.3 迁移策略记录

每个生成的脚本都包含 `metadata.migration_strategy`:

```json
{
  "preserved": ["Hook段快节奏2镜头模式", "CTA段紧迫感文字密度"],
  "strengthened": ["产品露出从8s提前到5s", "Proof增加对比画面"],
  "changed": ["Pain段从5段压缩为3段"],
  "strategy_brief": "保持原视频的快节奏Hook和紧迫CTA,强化产品展示和信任背书"
}
```

### 5.4 降级机制

```
LLM 调用 (最多3次重试)
  ├── 成功 → 验证 JSON 格式 → 后处理 → 保存
  ├── JSON 格式错误 → 自动修复 (Pydantic 校验)
  ├── 时长偏差 >25% → 拒绝, 重新生成
  └── 3次全部失败 → 使用模板 Fallback (从原结构构建基础脚本)
```

---

## 六、素材缺口识别与补全

### 6.1 缺口检测算法

```python
# GapDetector.detect(project_id) 检测流程:
# 1. 读取当前视频结构 (5个分镜槽位)
# 2. 读取用户上传的素材列表
# 3. 运行素材匹配 (AssetMatcher)
# 4. 对每个分镜槽位判断:

for segment in structure.script:
    if segment.assetId in user_asset_ids:  # 用户有素材 → 不是缺口
        continue
    if segment.id in matched_segment_ids:   # 匹配到了素材 → 不是缺口
        continue
    标记为缺口 → 生成缺口描述 + 推荐策略

# 缺口严重度分级:
# Hook和CTA缺口 → critical (严重影响视频效果)
# Pain/Product/Proof缺口 → warning

# 缺口描述示例:
"Hook缺口: 缺少开头吸引镜头，需要在0-2.7s制造视觉冲击，建议用冲突画面、悬念特写或产品反转"
"CTA缺口: 缺少转化引导镜头，需要价格优惠+行动引导画面，建议用促销视觉+紧迫感元素"
```

### 6.2 4策略补全引擎

```python
# 策略优先链 (按效果从高到低):
STRATEGY_ORDER = ["reorder", "packaging", "aigc", "recompose"]

# 策略1: reorder (结构重排)
# 适用: 有可匹配素材时
# 效果: 调用 AutoReorderService, 将已有素材推到更重要的分镜位置
# 约束: 锁定分镜不能被移动

# 策略2: packaging (包装补全)
# 适用: 始终可用
# 效果: 使用 Pillow 生成标题卡/卖点卡片 (带分镜类型标题 + 口播文案)
# 颜色按分镜类型区分 (Hook红/Pain紫/Product蓝/Proof绿/CTA金)

# 策略3: aigc (AI 生成补全)
# 适用: RunningHub ComfyUI 已配置
# 效果: 调用 ComfyUI Flux 生成 1080×1920 电商产品照
# 提示词从 PromptEngine 自动生成 (或 LLM 生成)
# 下载后存入素材库, 标记为 AIGC 来源

# 策略4: recompose (素材重组)
# 适用: 用户上传了视频素材
# 效果: 从视频中裁切片段, 智能定位到最相关的时间点
```

### 6.3 语义关键词扩展组

缺口检测时不只做精确标签匹配，还使用语义扩展:

```python
SEMANTIC_GROUPS = {
    "厨房": ["厨房场景", "灶台", "油烟", "锅具", "料理台", "烹饪"],
    "油污": ["油污", "脏污", "污垢", "重度污渍", "陈年污垢"],
    "美妆": ["面部特写", "膏体拉丝", "涂抹演示"],
    "食物": ["食物特写", "颗粒状产品", "彩色糖果", "咀嚼展示", "拉丝效果"],
    "数码": ["材质反光", "内部拆解"],
    "清洁": ["涂抹演示", "泡沫细腻", "液体流动"],
    "对比": ["颜色对比", "内部拆解", "Before/After"],
}
```

---

## 七、LLM 驱动 Flux 提示词工程

### 7.1 设计理念

电商产品图的 AI 生成需要**专业摄影级别的提示词**。简单的"好物推荐，电商带货风格"无法让 Flux 模型理解具体的产品特征。我们设计了一套 **6 层专业提示词结构**，由 LLM 根据产品信息自动生成。

### 7.2 6 层结构

```
Layer 1: COMPOSITION (构图)
  → 9:16 vertical medium close-up, centered framing
  → 拍摄角度: 15° slight overhead / eye-level
  → 裁切: tight crop focusing on product

Layer 2: SUBJECT (主体)
  → 产品名称、颜色数据 (来自 Vision API 分析)
  → 材质描述: glossy/metallic/matte/textured
  → 标签细节: logo embossing/texture patterns

Layer 3: LIGHTING (灯光)
  → 光比: 8:1 contrast ratio
  → 主光: 45° soft diffused key light
  → 轮廓光: hard back rim light
  → 补光: subtle fill at 7 o'clock
  → 产品类型特定灯光: food photography lighting / beauty ring light

Layer 4: ENVIRONMENT (环境)
  → 背景: seamless pure white / dark void / rustic wood
  → 道具: scattered crumbs / water droplets / product packaging
  → 氛围: warm and inviting / dramatic and striking

Layer 5: ACTION (动作)
  → 产品状态: slowly rotating / suspended mid-air / bursting through
  → 动态元素: crumbs flying / liquid pouring / steam rising
  → 分镜类型动作: dramatic reveal (Hook) / side-by-side (Proof)

Layer 6: TECHNICAL (技术参数)
  → 相机: Sony A7R V
  → 镜头: 100mm f/2.8 macro / 85mm f/1.4 prime
  → 景深: shallow depth of field
  → 画质: 8k resolution, hyperrealistic, professional color grading
  → 规格: commercial photography, photorealistic, masterpiece
```

### 7.3 LLM 提示词生成 Prompt

```python
FLUX_SYSTEM_PROMPT = """
You are a world-class AI commercial photographer and prompt engineer.
Create a detailed, professional-grade Flux prompt for a single product advertisement frame.

## CRITICAL RULES
- Output ONLY the raw prompt text. No quotes, no markdown, no explanations.
- Pure English. NO Chinese characters anywhere.
- 150-250 words. Be thorough and specific.

## PROMPT STRUCTURE
1. COMPOSITION: Specify the exact shot type, camera angle, and framing
2. SUBJECT: Describe the SPECIFIC product in extreme detail
3. LIGHTING: Name specific lighting setups (key light, rim light, fill light)
4. ENVIRONMENT: Describe the background and setting in detail
5. ACTION/DYNAMICS: What is happening in the frame
6. TECHNICAL: Camera specs, lens type, depth of field, resolution

## QUALITY REQUIREMENTS
- Use professional commercial photography vocabulary
- Include material properties: matte, glossy, metallic, textured, translucent
- Include lighting terms: soft diffused key light, hard rim light, golden hour
- Include camera terms: macro lens, 85mm prime, tilt-shift, bokeh
- Always end with: "commercial photography, hyperrealistic, 8k resolution, masterpiece"
"""
```

### 7.4 实际生成示例

**输入产品**: 趣多多巧克力曲奇 (食品饮料)

**LLM 生成的提示词** (1888 字符):

```
Composition: Vertical 9:16 medium close-up hero product framing, centered product
arrangement, eye-level camera angle optimized for 1080x1920 advertisement...

Subject: Official Qu Duoduo Chocolate Chip Cookies, warm golden-brown #D2691E
crisp outer crust, generously embedded matte dark chocolate chunks #8B4513, porous
flaky cracked edges, faint glossy sheen of melted chocolate...

Lighting: High contrast 8:1 light ratio setup, powerful hard back rim light carving
a glowing sharp outline, side studio strobe key light at 45 degrees, soft warm
golden fill light at 7 o'clock...

Environment: Seamless absolute white studio background, zero distracting elements,
designed to make the golden cookie pop instantly...

Action: The cookie slowly rotates on a minimalist turntable, catching the light on
different chocolate chunks as it turns...

Technical: Shot on Sony A7R V, 100mm f/2.8 macro lens, shallow depth of field with
tack sharp focus, native 9:16 aspect ratio, high dynamic range...
commercial photography, hyperrealistic, 8k resolution, masterpiece
```

**对比规则引擎**:
```
旧版 172 chars: "vertical 9:16 composition, food photography, beverage, drink, 
bold eye-catching shot, glossy, sparkling, golden texture, dramatic reveal..."
```

### 7.5 降级链

```
FluxPromptGenerator.generate()
  ├── LLM available?
  │     ├── YES → Doubao LLM 生成 6 层专业提示词 (~12s)
  │     │         ├── 成功 → 返回 (1888+ chars)
  │     │         └── 失败 → 降级 ↓
  │     └── NO  → 降级 ↓
  └── 降级: PromptEngine 规则引擎 (0ms, ~500 chars)
  ```

---

## 八、7 步视频渲染管道

### 8.1 Template Method 模式

借鉴 Pixelle-Video 的 LinearVideoPipeline 设计，将渲染过程分解为 7 个独立步骤:

```python
class VideoRenderPipeline:
    def run(self, *, job_id, project_id, version, resolution):
        ctx = RenderContext(...)
        self._prepare(ctx)              # Step 1
        self._synthesize_all_tts(ctx)   # Step 2 (Pixelle 模式)
        self._process_segments(ctx)     # Step 3
        self._apply_overlays(ctx)       # Step 4
        self._assemble_video(ctx)       # Step 5
        self._mix_audio(ctx)            # Step 6
        self._finalize(ctx)             # Step 7
        return ctx
```

### 8.2 各步详解

**Step 1: Prepare** — 加载数据、创建目录、分辨率自适应

```python
# 从分析结果读取原视频分辨率 (不是硬编码 1080×1920)
video_resolution = analysis_result["meta"]["resolution"]  # 如 "960×544"
ctx.width, ctx.height = int(w), int(h)
```

**Step 2: TTS 预合成** (Pixelle-Video 模式的精髓)

```python
# 先生成所有配音音频，再按音频实际时长调整画面
for idx, segment in enumerate(segments):
    tts.synthesize(script, output_path, target_duration=seg_dur)
    actual_duration = probe_duration(output_path)  # 实际音频时长
    segment.duration = max(actual_duration, 0.5)   # 画面匹配音频

# 重新计算时间线 (音频驱动的 duration)
cursor = 0.0
for seg in segments:
    seg.start = cursor
    seg.duration = max(seg.duration, 0.5)
    seg.end = cursor + seg.duration
    cursor = seg.end
```

**Step 3: 逐段处理** — 核心渲染逻辑

```python
for idx, segment in enumerate(segments):
    if 无素材:
        # LLM 生成 Flux 提示词 (~12s)
        flux_prompt = FluxPromptGenerator.generate(
            segment_type, script, visual, camera, emotion,
            product_name, product_type, vision_tags, vision_colors
        )
        # ComfyUI Flux 文生图 (~60s, 1080p)
        visual = comfyui.generate_image(prompt=flux_prompt, w=ctx.width, h=ctx.height)
        
        # 用户选择了视频模式?
        if segment_modes[id] == "video":
            # WAN 2.2 图生视频 (~150s, 512p)
            video = comfyui.generate_video(prompt, image_path=visual)
            # 归一化为标准格式
            ffmpeg(video → h264/aac/yuv420p) → seg_000.mp4
        else:
            # Flux 图片 + FFmpeg 运镜 (静态→动态)
            ffmpeg(visual + camera_motion + visual_fx) → seg_000.mp4
    
    elif 有图像素材:
        ffmpeg(素材 + 运镜) → seg_000.mp4
    
    elif 有视频素材:
        ffmpeg(素材裁剪 + 缩放) → seg_000.mp4
    
    # 合并 TTS 配音
    ffmpeg(seg_000.mp4 + seg_000_tts.mp3) → seg_000.mp4
```

**Step 4: 动画叠加** — Hook/CTA 分镜的视觉增强

```python
# 使用 Pillow 生成弹入/缩放等动画帧
# 用 FFmpeg overlay 滤镜叠加
for segment in segments:
    if segment.type in ("cta", "hook"):
        overlay = create_animated_overlay(text, animation="pop_in")
        ffmpeg(seg.mp4 + overlay.mp4, "overlay=0:0") → seg_animated.mp4
```

**Step 5: 视频拼接**

```python
# FFmpeg concat 滤镜 (要求所有分镜格式一致)
ffmpeg -i seg_000.mp4 -i seg_001.mp4 ... \
  -filter_complex "[0:v][0:a][1:v][1:a]...concat=n=5:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  output.mp4
```

**Step 6: BGM 混音**

```python
# librosa 节拍检测 → 分镜切点对齐
beats = librosa.beat.beat_track(y=audio, sr=sample_rate)
for seg in segments:
    nearest_beat = min(beats, key=lambda b: abs(b - seg.start))
    if |nearest_beat - seg.start| ≤ 0.15:
        seg.start = nearest_beat  # 微调到最近节拍

# FFmpeg amix 混音
ffmpeg -i video.mp4 -i bgm.mp3 \
  -filter_complex "[1:a]volume=0.25[bgm];[0:a][bgm]amix=duration=first" \
  output_bgm.mp4
```

**Step 7: 自审计**

```python
# 统计 AI 生成 vs 回退
flux_segments = count(segments where flux image exists)
pillow_segments = count(segments where prompt card exists)

# 存入 metadata
self_audit = {
    "visual_generation": {
        "method": "ComfyUI Flux" if flux_count > 0 else "Prompt Card",
        "quality": "excellent" | "good" | "basic" | "fallback",
        "flux_segments": flux_count,
        "per_segment": {"0": "flux", "1": "wan2.2", ...}
    },
    "audio_generation": {
        "method": "Edge TTS" | "None"
    }
}
```

### 8.3 TTS 驱动时长设计

这是从 Pixelle-Video 借鉴的关键架构决策:

```
传统做法: LLM 估算每个分镜时长 → 生成画面 → 合成 TTS → TTS 可能太长/太短
StructForge: LLM 估算时长 → 先生成 TTS → 用实际音频时长驱动画面 → 完美匹配

效果: 画面时长 = 配音时长, 永远不会出现"画面结束了配音还在说"或"配音完了画面还在放"的情况
```

---

## 九、前端交互与可视化

### 9.1 页面结构 (7 页)

| 页面 | 路由 | 功能 |
|------|------|------|
| 项目列表 | `/projects` | 创建/删除项目, 卡片式布局 |
| 分析台 | `/analyze` | 视频上传, 分析进度, 结构展示, 多样例管理 |
| 编辑台 | `/migrate/:id` | 创作简报, 产品图上传, 缺口识别, NL编辑, 脚本生成 |
| 结果展示台 | `/result/:id` | Storyboard Review, 逐段生成选择, 视频播放, 时间线, 导出 |
| 历史记录 | `/history` | 项目历史画廊, 状态筛选, 搜索 |
| 系统设置 | `/settings` | 服务状态, LLM Ping, 环境变量参考 |
| 404 | `*` | 未找到页面 |

### 9.2 关键交互

**Storyboard Review (Director's Cut)**:
- 每个分镜展示: 编号、类型标识、口播文案、时长进度条、来源标签 (AI/原始)
- AI 分镜右上角: 生图/生视频 切换按钮
- 底部: [复制 Flux 提示词] 按钮 (LLM 生成的完整 6 层提示词)
- 顶部: RENDER ALL 按钮 (显示 "生成 N 图 + M 视频")

**素材缺口识别面板**:
- 每个缺口卡片: 分镜名称、严重度 (⚠️关键/缺口)、描述、可用策略标签
- 渲染说明: "渲染时 ComfyUI Flux 将自动为缺失画面生成 AI 图片"

**实时渲染进度**:
- SSE (Server-Sent Events) 推送进度
- 每个分镜完成时显示 ✅ 标记
- 当前处理的显示 🔄 标记

### 9.3 设计系统

**Swiss Spa Premium 美学**:
- 暖白色调: #FAFAF9 (底色) + #FFFFFF (卡片)
- 金色主色: #C8843C (按钮/强调/高亮)
- 绿色辅色: #4A9E7C (成功/通过/健康)
- 柔和边框: border/60 透明度
- 统一圆角: border-xl (16px)
- 极浅阴影: shadow-sm (1px blur)
- 字体: Inter + JetBrains Mono
- 67 个组件风格统一

### 9.4 状态管理

Zustand 集中式状态管理 (37 个字段, 36 个 actions):

```typescript
interface AppState {
  // 项目
  projects: Project[]
  activeProjectId: string | null
  
  // 分析
  videoFile: File | null
  isAnalyzing: boolean
  analysisResult: VideoStructure | null
  analysisSamples: AnalysisSample[]
  
  // 脚本
  currentStructure: VideoStructure | null
  currentScript: FinalScript | null
  scriptLoading: boolean
  
  // 渲染
  renderJobId: string | null
  renderStatus: RenderStatus
  renderProgress: number
  renderWarnings: string[]
  outputUrl: string | null
  
  // UI
  sidebarCollapsed: boolean
  toasts: ToastMessage[]
  apiError: string | null
}
```

### 9.5 API 通信

```typescript
// 前端 API 客户端 (src/services/api.ts)
// 30 个 RESTful API 方法, 统一错误处理, 指数退避重试

const api = {
  // 项目
  listProjects, createProject, updateProject, deleteProject,
  
  // 分析
  startAnalysis, getAnalysis, listAnalysisSamples, selectAnalysisReference,
  
  // 结构
  getStructure, updateSegment, reorderSegments, undo, redo,
  nlEditStructure,  // 自然语言编辑
  
  // 素材
  listAssets, analyzeAsset, matchAssets,
  
  // 缺口
  listGaps, fixGap, fixAllGaps,
  
  // 迁移
  migrateScript, getFinalScript, getResultVersions,
  
  // 渲染
  startRender, getRenderJob, upgradeSegmentToVideo,
  
  // 工具
  getCapabilities, getWaveform, getThumbnail, getBlueprintPayloads
};
```

---

## 十、技术栈详解

| 层 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **前端框架** | React + TypeScript | 18.x | SPA 7 页面 |
| **构建工具** | Vite | 5.x | 开发服务器 + 构建 |
| **样式** | Tailwind CSS | 3.x | Swiss spa 设计系统 |
| **状态管理** | Zustand | 4.x | 集中式状态 (persisted) |
| **路由** | React Router | 6.x | 客户端路由 |
| **图标** | Lucide React | — | 统一图标库 |
| **后端框架** | FastAPI | 0.x | REST API (自动 OpenAPI 文档) |
| **数据校验** | Pydantic | 2.x | StrictModel (extra=forbid) |
| **数据库** | SQLAlchemy + SQLite | 2.x | 嵌入式零配置 |
| **LLM** | Doubao Seed 2.0 | — | 结构提取 + 脚本迁移 + 提示词 |
| **视觉 AI** | Doubao Vision API | — | 产品图分析 |
| **语音识别** | Volcano BigModel ASR | v3 | 样例视频转写 |
| **图像生成** | ComfyUI Flux (RunningHub) | — | 文生图 1080p |
| **视频生成** | WAN 2.2 (RunningHub) | — | 图生视频 512p |
| **语音合成** | Edge TTS | — | 免费配音 |
| **视频处理** | FFmpeg | 8.x | 场景检测/合成/字幕 |
| **图像处理** | Pillow | 11.x | 蓝图卡渲染 |
| **HTTP 客户端** | httpx | — | 异步 API 调用 |
| **测试** | Vitest + Pytest | — | 前后端测试 |

---

## 十一、AI 工具使用声明

### 11.1 使用的 AI 工具

| 工具 | 提供商 | 用途 | 环节 |
|------|------|------|------|
| Doubao LLM (豆包 Seed 2.0) | 字节跳动火山引擎 | 视频结构提取、脚本迁移生成、Flux 提示词生成 | 分析/迁移 |
| Doubao Vision | 字节跳动火山引擎 | 产品图片标签提取、颜色识别、OCR 文字识别、品类推断 | 分析 |
| Volcano BigModel ASR | 字节跳动火山引擎 | 样例视频语音转写 (v3 API) | 分析 |
| RunningHub ComfyUI | RunningHub | Flux 文生图 (电商产品照)、WAN 2.2 图生视频 | 生成 |
| Edge TTS | 微软 | 免费中文语音合成 (配音) | 生成 |
| Claude Code | Anthropic | 编码实现、代码审查、架构优化、Bug 修复 | 开发全流程 |

### 11.2 自主设计与实现声明

以下核心能力由参赛者自主设计实现，**未**依赖现成产品直接生成:

| 自主设计 | 说明 |
|------|------|
| **5 段说服心理学结构模型** | 自主定义电商视频的 5 段叙事框架 + 5 维制作参数体系 |
| **LLM 结构迁移 Prompt 工程** | 自建 10,000 字符的完整迁移 prompt，包含结构骨架、L2 节奏数据、健康度诊断、风格量化参数、分镜类型速查表 |
| **4 策略缺口检测引擎** | 自主设计 4 策略引擎 (reorder/packaging/aigc/recompose) + 9 组语义关键词扩展 |
| **FluxPromptGenerator** | 自建 6 层专业电商摄影提示词结构 (构图/主体/灯光/环境/动作/技术)，由 LLM 驱动生成 |
| **7 步视频渲染管道** | Template Method 模式自主实现，含 TTS 驱动时长、分辨率自适应、逐段生成 |
| **Swiss spa 设计系统** | 自建 67 组件统一设计，暖白+金色+绿色调色板 |
| **前后端全栈架构** | React+TypeScript+Zustand 前端，Python+FastAPI+Pydantic 后端，自建 50+ API 端点 |

### 11.3 竞品参考 (仅调研，未复制源码)

| 竞品 | 参考内容 |
|------|------|
| Pixelle-Video | ComfyUI/RunningHub 集成模式、Template Method 管道设计模式 |
| 剪映/CapCut | 视频创作交互形态、分镜时间线设计 |
| Runway | AI 视频生成的产品设计思路 |

---

## 十二、安全边界

### 12.1 API Key 保护

```
存储: 仅服务端 .env 文件 (已加入 .gitignore)
传输: 后端代理所有 AI API 调用，前端不直接访问任何第三方 API
前端: 零 API Key 暴露，所有请求通过 POST /api/v1/* 代理
```

### 12.2 内容安全

```python
# ContentSafetyService: 可配置关键词拦截列表
content_safety_enabled: bool = False  # 默认关闭，按需启用
content_safety_blocked_terms: str = "" # 拦截关键词，逗号分隔

# 在 LLM 生成脚本后运行检查:
if settings.content_safety_enabled:
    result = safety.check_script(script)
    if result.blocked:
        raise MigrationError("内容安全检查阻止")
    if result.warnings:
        script.metadata["warnings"].extend(warnings)
```

### 12.3 文件上传安全

```python
# 上传大小限制
max_upload_bytes: int = 500 * 1024 * 1024  # 500MB

# 文件类型白名单
SUPPORTED_TYPES = {
    "image": ("image/",),
    "video": ("video/",),
    "text": ("text/plain",),
}

# MIME 类型验证
def validate_upload_metadata(content_type, filename, size_bytes, settings):
    if size_bytes > settings.max_upload_bytes:
        raise UploadValidationError("文件过大")
    if not is_supported_type(content_type):
        raise UploadValidationError("不支持的文件类型")
```

### 12.4 数据存储

```
数据库: SQLite 嵌入式 (本地文件)
存储内容: 分析结果、项目信息、素材元数据、脚本版本
不上传: 不向任何第三方服务器上传用户数据
删除策略: DELETE /api/v1/projects/{id} 级联删除所有关联数据
```

### 12.5 API 鉴权

```python
# 可选 API Key 中间件 (生产环境)
class APIKeyMiddleware:
    def __init__(self, app, api_key):
        self.api_key = api_key
    
    async def __call__(self, scope, receive, send):
        if scope["path"].startswith("/api/"):
            key = headers.get("x-api-key")
            if key != self.api_key:
                return JSONResponse({"detail": "Unauthorized"}, 401)
```

---

## 十三、本地部署指南

### 13.1 环境要求

- Python 3.12+
- Node.js 18+
- FFmpeg (命令行可访问)
- Git

### 13.2 获取代码

```bash
git clone https://github.com/dinosaur-006/structforge.git
cd structforge
```

### 13.3 配置 API Key

```bash
cd ai-services
copy .env.example .env
```

编辑 `.env` 文件，填入你的 API Key:

```env
# 必需: LLM (结构提取 + 脚本迁移 + 提示词生成)
STRUCTFORGE_DOUBAO_LLM_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3/chat/completions
STRUCTFORGE_DOUBAO_LLM_API_KEY=your-doubao-api-key
STRUCTFORGE_DOUBAO_LLM_MODEL=ep-xxxxxxxxxxxx-xxxxx

# 必需: AI 图片生成 (RunningHub ComfyUI Flux)
STRUCTFORGE_RUNNINGHUB_API_KEY=your-32-char-runninghub-key

# 可选: 语音转写 (火山 ASR, 用于样例视频字幕提取)
STRUCTFORGE_VOLCANO_ASR_ENDPOINT=https://openspeech.bytedance.com/api/v1/asr
STRUCTFORGE_VOLCANO_ASR_API_KEY=your-asr-access-token
STRUCTFORGE_VOLCANO_ASR_RESOURCE_ID=volc.seedasr.auc

# 可选: 产品图视觉分析 (不填则自动使用 LLM 配置)
STRUCTFORGE_DOUBAO_VISION_ENDPOINT=
STRUCTFORGE_DOUBAO_VISION_API_KEY=

# 任务执行模式 (开发环境使用本地同步)
STRUCTFORGE_CELERY_TASK_ALWAYS_EAGER=true
```

### 13.4 安装依赖

**后端**:
```bash
cd ai-services
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**前端**:
```bash
# 回到项目根目录
npm install
```

### 13.5 启动服务

**后端** (端口 8000):
```bash
cd ai-services
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**前端** (端口 5173):
```bash
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`

### 13.6 使用流程

1. 打开浏览器 → 自动跳转到分析台
2. 拖拽上传一条电商带货视频 (15-45秒)
3. 等待 AI 分析完成 (~60秒) → 查看 3 类结构拆解结果
4. 点击"下一步" → 输入产品名和卖点
5. 可选: 上传产品图片 (Vision AI 会分析后优化生图效果)
6. 选择脚本风格 → 点击"生成视频脚本"
7. 在结果展示台逐段选择生成模式 (生图/生视频)
8. 点击 RENDER ALL → 等待渲染完成 → 播放视频
9. 导出: 脚本 JSON / 字幕 SRT / 视频 MP4

---

## 十四、项目结构详解

```
structforge/
├── ai-services/                    # Python 后端
│   ├── main.py                     # FastAPI 应用工厂, 注册 50+ 路由
│   ├── config.py                   # Pydantic Settings, 37 个配置项
│   ├── seed.py                     # Demo 种子数据
│   │
│   ├── models/
│   │   ├── schemas.py              # 46 个 Pydantic StrictModel
│   │   └── repository.py           # SQLiteRepository (6 表, 60+ 方法)
│   │
│   ├── routes/                     # 9 个 API 路由文件
│   │   ├── projects.py             # 项目 CRUD
│   │   ├── structure.py            # 结构编辑 (11 端点, 含 NL 编辑)
│   │   ├── assets.py               # 素材管理 + 匹配
│   │   ├── gaps.py                 # 缺口检测 + 修复
│   │   ├── migrate.py              # 脚本迁移
│   │   ├── render.py               # 视频渲染 + SSE 流
│   │   ├── optimize.py             # 波形/缩略图/蓝图
│   │   └── audit_api.py            # 爆款审计
│   │
│   ├── services/                   # 50+ 核心服务模块
│   │   ├── pipeline.py             # 视频分析: 场景检测→ASR→Vision→LLM
│   │   ├── migrator.py             # 脚本迁移: LLM 生成→后处理→评分
│   │   ├── render_pipeline.py      # 7 步视频渲染: TTS→Flux→WAN→FFmpeg
│   │   ├── gap_detector.py         # 4 策略缺口检测引擎
│   │   ├── gap_filler.py           # 缺口修复: ComfyUI/Pillow/reorder
│   │   ├── flux_prompt_generator.py # LLM 驱动 6 层提示词生成
│   │   ├── comfyui_service.py      # RunningHub ComfyUI 集成
│   │   ├── llm_client.py           # LLM 客户端: 指数退避重试
│   │   ├── llm_structure.py        # LLM 结构提取
│   │   ├── asr.py                  # 火山 ASR v3 转写
│   │   ├── vision.py               # 豆包 Vision 视觉分析
│   │   ├── tts_engine.py           # Edge TTS 语音合成
│   │   ├── bgm_engine.py           # BGM 节拍检测 + 混音
│   │   ├── asset_matcher.py        # 素材匹配 (规则引擎)
│   │   ├── structure_editor.py     # 结构编辑器 (undo/redo 持久化)
│   │   ├── nl_editor.py            # 自然语言编辑 (LLM 解析)
│   │   ├── result_evaluator.py     # 版本评分 (规则引擎)
│   │   ├── burst_metrics.py        # 41 项爆款指标
│   │   ├── burst_auditor.py        # 全模态审计
│   │   ├── cover_generator.py      # 封面图生成
│   │   ├── highlight_detector.py   # 高光片段检测
│   │   ├── scene_classifier.py     # 场景分类
│   │   ├── transition_advisor.py   # 转场推荐
│   │   ├── overlay_advisor.py      # 贴纸推荐
│   │   ├── content_safety.py       # 内容安全审查
│   │   ├── auth.py                 # API Key 中间件
│   │   ├── generation_notifier.py  # WebSocket 实时通知
│   │   ├── renderer_abstraction.py # 渲染引擎抽象工厂
│   │   ├── animated_overlay.py     # 动画叠加层
│   │   ├── blueprint_renderer.py   # 蓝图卡渲染
│   │   └── prompt_engine/          # 提示词引擎 (vocabulary+assembler+engine)
│   │
│   ├── tasks/                      # 异步任务
│   │   ├── analyze.py              # 分析任务分发
│   │   └── render.py               # 渲染任务分发
│   │
│   └── templates/
│       └── product_hero.html       # 产品展示 HTML 模板
│
├── src/                            # React 前端
│   ├── main.tsx                    # 入口 + 错误边界
│   ├── App.tsx                     # 根组件
│   ├── router.tsx                  # 路由配置 (7 页 + 重定向)
│   ├── index.css                   # 全局样式 (Swiss spa)
│   │
│   ├── pages/                      # 7 个页面
│   │   ├── AnalyzePage.tsx         # 分析台
│   │   ├── MigratePage.tsx         # 编辑台
│   │   ├── ResultPage.tsx          # 结果展示台
│   │   ├── ProjectListPage.tsx     # 项目列表
│   │   ├── HistoryPage.tsx         # 历史记录
│   │   ├── SettingsPage.tsx        # 系统设置
│   │   └── NotFoundPage.tsx        # 404
│   │
│   ├── components/                 # 40+ 组件
│   │   ├── analyze/                # 分析相关 (12 组件)
│   │   ├── migrate/                # 编辑相关 (7 组件)
│   │   ├── result/                 # 结果相关 (10 组件)
│   │   ├── layout/                 # 布局 (AppLayout + WorkflowSteps)
│   │   ├── shared/                 # 共享 (FAQPanel + LLMOutagePanel)
│   │   └── ui/                     # 基础 UI (15 组件)
│   │
│   ├── store/
│   │   └── index.ts                # Zustand 状态管理 (775 行)
│   │
│   ├── services/
│   │   └── api.ts                  # API 客户端 (30 方法)
│   │
│   └── shared/                     # 工具 (types/cn/format/copy/download/i18n/keybindings)
│
├── docs/                           # 项目文档 (40+ 文件)
│   ├── StructForge-赛题交付文档.md  # 本文件
│   ├── PROJECT.md                  # 项目说明
│   ├── AI_TOOLS.md                 # AI 工具声明
│   ├── DEMO.md                     # 演示方案
│   └── 演示话术逐字稿.md            # 演示脚本
│
├── tailwind.config.js              # Tailwind 配置 (Swiss spa 调色板)
├── vite.config.ts                  # Vite 构建配置
├── package.json                    # 前端依赖
├── requirements.txt                # 后端依赖 (ai-services/)
├── .gitignore                      # 忽略 .env/.venv/node_modules/__pycache__
└── README.md                       # 项目首页
```

---

## 附录 A: API 端点清单 (50 路由)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/capabilities` | AI 能力状态 |
| GET | `/api/v1/projects` | 项目列表 |
| POST | `/api/v1/projects` | 创建项目 |
| GET | `/api/v1/projects/{id}` | 项目详情 |
| PUT | `/api/v1/projects/{id}` | 更新项目 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |
| POST | `/api/v1/projects/{id}/product-image` | 产品图分析 |
| POST | `/api/v1/analyze` | 开始分析 |
| GET | `/api/v1/analyze/{job_id}` | 分析进度 |
| GET | `/api/v1/analyze/{job_id}/stream` | 分析进度 SSE |
| GET | `/api/v1/analyze/project/{id}/samples` | 样例列表 |
| PUT | `/api/v1/analyze/project/{id}/reference/{jid}` | 选择参考样例 |
| GET/PUT/POST/DELETE | `/api/v1/structure/{id}/*` | 结构 CRUD + 重排 + undo/redo + reset + NL 编辑 |
| POST/GET | `/api/v1/assets/*` | 素材上传/列表/匹配/缩略图 |
| GET | `/api/v1/gaps/{id}` | 缺口检测 |
| POST | `/api/v1/gaps/{id}/fix` | 单个修复 |
| POST | `/api/v1/gaps/{id}/fix-all` | 全部修复 |
| GET/POST | `/api/v1/migrate/{id}/*` | 脚本生成/变体/版本 |
| POST/GET/DELETE | `/api/v1/render/*` | 渲染/取消/查询/SSE/视频升级 |
| GET | `/api/v1/optimize/{id}/*` | 波形/缩略图/蓝图 |
| POST/GET | `/api/v1/audit/*` | 爆款审计 |
| POST | `/api/v1/image/generate` | AI 生图 |
| POST | `/api/v1/media/preview` | 媒体预览 |
| GET | `/api/v1/templates` | 模板列表 |
| GET | `/api/v1/pipelines` | 管道列表 |
| GET | `/api/v1/diagnostics/llm` | LLM 诊断 |

## 附录 B: 配置项清单 (37 项)

| 配置项 | 默认值 | 必需 | 说明 |
|------|------|:--:|------|
| `STRUCTFORGE_DOUBAO_LLM_ENDPOINT` | — | ✅ | LLM API 端点 |
| `STRUCTFORGE_DOUBAO_LLM_API_KEY` | — | ✅ | LLM API Key |
| `STRUCTFORGE_DOUBAO_LLM_MODEL` | `doubao-seed-2-0-lite` | ✅ | LLM 模型名 |
| `STRUCTFORGE_RUNNINGHUB_API_KEY` | — | ✅ | ComfyUI API Key |
| `STRUCTFORGE_VOLCANO_ASR_API_KEY` | — | 可选 | ASR API Key |
| `STRUCTFORGE_VOLCANO_ASR_RESOURCE_ID` | `volc.seedasr.auc` | 可选 | ASR 资源ID |
| `STRUCTFORGE_DOUBAO_VISION_API_KEY` | — | 可选 | Vision API Key |
| `STRUCTFORGE_DOUBAO_IMAGE_API_KEY` | — | 可选 | Seedream 生图 |
| `STRUCTFORGE_TTS_API_KEY` | — | 可选 | 火山 TTS |
| `STRUCTFORGE_COMFYUI_VIDEO_ENABLED` | `false` | 可选 | WAN2.2 视频 |
| `STRUCTFORGE_CONTENT_SAFETY_ENABLED` | `false` | 可选 | 内容安全 |
| `STRUCTFORGE_CELERY_TASK_ALWAYS_EAGER` | `false` | 可选 | 任务模式 |
