# StructForge AI 视频生成模块 — 完整设计文档

> 版本: 1.0  
> 日期: 2026-06-09  
> 状态: 设计完成，待实施

---

## 目录

1. [模块定位与设计目标](#1-模块定位与设计目标)
2. [系统架构](#2-系统架构)
3. [AI 视频生成服务](#3-ai-视频生成服务)
4. [多层级提示词引擎](#4-多层级提示词引擎)
5. [平台适配器设计](#5-平台适配器设计)
6. [品类自适应词汇系统](#6-品类自适应词汇系统)
7. [质量验证器](#7-质量验证器)
8. [前端展示设计](#8-前端展示设计)
9. [与现有系统的集成](#9-与现有系统的集成)
10. [实施计划](#10-实施计划)
11. [答辩话术参考](#11-答辩话术参考)

---

## 1. 模块定位与设计目标

### 1.1 现状与痛点

当前 StructForge 在视频生成阶段，对于没有用户上传素材的分镜，采用 Pillow 绘制"蓝图卡片"作为占位画面。存在以下问题：

| 痛点 | 表现 |
|------|------|
| **能力不可见** | 用户看不到系统具备 AI 视频生成能力，只看到一张静态卡片 |
| **提示词不可得** | 文生视频的 prompt 只在 Payload 抽屉中，需要额外点击才能看到 |
| **架构耦合** | AI 视频生成逻辑内嵌在 `compositor.py` 中，无法独立迭代 |
| **平台不通用** | 当前只针对 Seedance，无法适配 Runway/Kling/Sora |
| **提示词质量无保障** | `build_master_prompt()` 是简单的字符串拼接，没有结构化设计 |

### 1.2 设计目标

1. **独立模块**：AI 视频生成从 `compositor.py` 中解耦，成为独立的 `ai_video_service`
2. **能力可见**：未连接 API 时，在视频播放器上直接展示完整的文生视频提示词，用户可复制到外部平台使用
3. **多平台适配**：支持 Seedance、Runway、Kling 三种主流平台，可扩展至 Sora
4. **提示词工程化**：建立五层结构化提示词引擎，品类自适应，质量可验证
5. **零破坏集成**：与现有 compositor/migrator/frontend 完全兼容

### 1.3 核心设计原则

> **"我们没有调用 AI"→"我们有完整的 AI 生成能力，只是没接 API Key"**

当 API 未配置时，系统不报错、不假装有视频，而是输出**可直接交付给下游渲染团队的专业提示词卡片**——包含完整 prompt、制作参数、API payload 和成本预估。

---

## 2. 系统架构

### 2.1 整体数据流

```
用户上传视频 → 分析 → 结构提取 → 迁移生成 FinalScript
                                        │
                          ┌─────────────┴─────────────┐
                          │  有素材的分镜               │  无素材的分镜
                          ▼                            ▼
                    compositor 原逻辑          AIVideoService.generate()
                          │                            │
                          │              ┌─────────────┴─────────────┐
                          │              │ API Key 已配置             │  API Key 未配置
                          │              ▼                            ▼
                          │        Seedance API               PromptCard
                          │              │                      (提示词+参数)
                          │              ▼                            │
                          │         真实视频                   prompt_card_renderer
                          │              │                            │
                          └──────────────┴────────────┬───────────────┘
                                                      ▼
                                              FFmpeg 合成
                                              (字幕+TTS+BGM)
                                                      │
                                                      ▼
                                                 最终 MP4
```

### 2.2 模块层次

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                            │
│  VideoPlayer (提示词展示) | PayloadPreviewDrawer (导出)      │
│  ResultTimeline (AI分镜标记)                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP API
┌──────────────────────────┴──────────────────────────────────┐
│                    Service Layer                             │
│  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │ AIVideoService   │  │  PromptEngine                    │ │
│  │ - generate()     │  │  - assemble()   五层结构组装     │ │
│  │ - PromptCard     │  │  - validate()   质量验证         │ │
│  │ - GeneratedVideo │  │  - adapt()      平台适配         │ │
│  └────────┬────────┘  └──────────────┬───────────────────┘ │
│           │                          │                       │
│  ┌────────┴──────────────────────────┴───────────────────┐ │
│  │              Platform Adapters                         │ │
│  │  SeedanceAdapter  │  RunwayAdapter  │  KlingAdapter    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. AI 视频生成服务

### 3.1 文件: `ai-services/services/ai_video_service.py`

```python
class AIVideoService:
    """
    独立的 AI 视频生成模块。与 compositor 完全解耦。

    职责:
    - 当 API Key 已配置 → 调用 Seedance/Runway/Kling → 返回真实视频
    - 当 API Key 未配置 → 返回 PromptCard（完整提示词+制作参数+API payload）
    """

    def __init__(self, settings: Settings, platform: str = "seedance"):
        self.settings = settings
        self.platform = platform
        self.prompt_engine = AIVideoPromptEngine(platform=platform)
        self.api_available = bool(settings.doubao_image_api_key)

    def generate(self, segment: FinalSegment) -> GeneratedVideo | PromptCard:
        """为单个分镜生成 AI 视频或返回提示词卡片"""
        prompt_result = self.prompt_engine.assemble(segment)
        if self.api_available:
            return self._call_seedance(prompt_result, segment)
        return PromptCard.from_prompt_result(prompt_result, segment)


@dataclass
class PromptCard:
    """当 API 不可用时返回的提示词卡片数据"""
    segment_id: str
    segment_type: str
    prompt_text: str              # 完整的文生视频提示词
    negative_prompt: str          # 负向提示词
    prompt_english: str           # 英文版 prompt（Runway 兼容）
    prompt_chinese: str           # 中文版 prompt（Kling 兼容）
    camera: str                   # 运镜指令
    visual_fx: str                # 视觉效果
    emotion: str                  # 情绪基调
    duration: float               # 目标时长
    aspect_ratio: str = "9:16"
    resolution: str = "720p"
    api_endpoint: str             # API 端点 URL
    api_payload: dict             # 完整 JSON 请求体
    estimated_cost: float         # 预估成本
    estimated_tokens: int         # 预估 Token
    subtitle_text: str            # 该分镜的字幕文案
    platform_compatible: list[str] # 兼容的平台列表


@dataclass
class GeneratedVideo:
    """API 调用成功后返回的真实视频"""
    segment_id: str
    video_path: Path
    duration: float
    platform: str
    generation_time: float       # API 调用耗时
    cost: float                  # 实际消耗
```

### 3.2 与 compositor 的集成

```python
# compositor.py 中的变更（伪代码）

# 之前:
if not shot_used and is_reference:
    video_gen = VideoGenerator(...)
    if video_gen.available:
        gen_path = work_dir / f"segment_{index:03d}_aivideo.mp4"
        video_gen.generate(prompt, gen_path, ...)

# 之后:
ai_video = AIVideoService(self.settings, platform="seedance")
if not shot_used and needs_ai_generation:
    result = ai_video.generate(segment)
    if isinstance(result, GeneratedVideo):
        source_path = result.video_path  # 使用真实视频
    elif isinstance(result, PromptCard):
        # 渲染提示词卡片 → 转视频 → 叠加字幕/TTS
        card_path = prompt_card_renderer.render(result)
        source_path = card_path
```

---

## 4. 多层级提示词引擎

### 4.1 文件: `ai-services/services/prompt_engine/engine.py`

### 4.2 五层提示词结构

这是所有平台适配器的统一输出格式。按**优先级顺序**排列，前30词权重最高。

```
Layer 1: SUBJECT（主体）          — 谁/什么在画面中              [权重: 35%]
Layer 2: ACTION（动作）           — 主体在做什么                  [权重: 20%]
Layer 3: CAMERA（镜头语言）       — 景别 + 运动 + 角度            [权重: 20%]
Layer 4: STYLE（风格/光影）       — 光照 + 色调 + 质感            [权重: 15%]
Layer 5: CONSTRAINTS（约束）      — 负向提示词 + 技术参数          [权重: 10%]
```

### 4.3 Layer 1: SUBJECT — 主体描述

**规则**：
- 放在最前面（前30词权重最高）
- 单一主体最优，避免画面拥挤
- 材质+颜色+状态同时描述，不使用抽象形容词
- 禁止使用"漂亮的""高级的""很好的"等空洞词汇

**品类→词汇映射表**（从 `vocabulary.py` 加载）:

| 品类 | 子类 | Subject 模板 |
|------|------|-------------|
| 食品饮料 | 液体类 | `{brand} {color} beverage pouring into a {container}, {texture} liquid, condensation droplets` |
| 食品饮料 | 零食类 | `crispy {product} sticks with {seasoning} flakes, glossy {sauce} coating, scattered {garnish}` |
| 食品饮料 | 乳制品 | `creamy white milk swirling in a glass, fresh dairy texture, soft white foam forming on top` |
| 美妆护肤 | 膏体类 | `pearly white cream being squeezed from a tube, smooth velvety texture, soft focus` |
| 美妆护肤 | 液体类 | `transparent golden serum dripping from a glass dropper, viscous slow flow, light reflection` |
| 电子3C | 手机 | `sleek smartphone with {color} metallic finish, edge-to-edge display lighting up with {app}` |
| 电子3C | 耳机 | `matte black earbuds floating in air, subtle {color} LED indicator glow, premium texture` |
| 服饰纺织 | 面料 | `flowing {fabric} fabric draped elegantly, {pattern} texture visible, soft natural folds` |

### 4.4 Layer 2: ACTION — 动作描述

**规则**：
- 现在时，单个动词短语
- 写慢、写连续（slow/gentle/continuous/smooth）
- 避免"快速""剧烈""突然"等导致画面崩溃的词汇

**产品动作词汇库**:

| 动作类型 | 词汇 |
|---------|------|
| 展示类 | slowly rotating on a turntable, elegantly sliding into frame, floating centered in frame |
| 使用类 | being gently poured, being squeezed out, being applied with fingertips |
| 特写类 | macro close-up revealing intricate texture, slow focus pull to product label |
| 冲击类 | dramatically splashing into crystal-clear water, bursting with fresh particles |
| 倒出类 | golden liquid streaming smoothly from bottle, thick sauce drizzling over food |
| 撕开类 | packaging being torn open in slow motion, fresh aroma visibly rising |

### 4.5 Layer 3: CAMERA — 镜头语言

**规则**：
- 景别 + 运动 + 速度，**每次只用一种运动**
- 速度用标量: slow/medium/fast，禁止模糊描述
- 复合运动（推镜+横摇）写成节奏分段，不塞进一个从句

**景别**:

| 景别 | 英文 | 适用场景 |
|------|------|---------|
| 大特写 | Extreme Close-Up (ECU) | 产品材质、logo、成分表、水滴 |
| 特写 | Close-Up (CU) | 产品占画面70%+，英雄镜头 |
| 中近景 | Medium Close-Up (MCU) | 手持产品、使用场景 |
| 中景 | Medium (MS) | 人物半身、产品+桌面环境 |

**运动（三平台对照）**:

| 中文 | Seedance | Runway | Kling |
|------|---------|--------|-------|
| 推近 | Dynamic fast 3D camera zoom-in / Cinematic slow push-in tracking shot | Slow dolly-in, gentle push toward subject | 镜头缓缓推近，画面逐渐聚焦到产品 |
| 拉远 | Slow dramatic pull-back reveal, wide establishing shot | Slow dolly-out, reveal context | 镜头慢慢拉远，视野逐渐开阔 |
| 横移 | Elegant dolly tracking shot, horizontal sweeping view | Slow pan right, controlled horizontal reveal | 镜头水平横移，展示产品侧面 |
| 手持 | Intense realistic handheld camera shake, chaotic aesthetic | Handheld phone camera, slight natural sway | 手持镜头轻微晃动，真实临场感 |
| 静态 | Locked-off stable tripod shot, hyper-focused framing | Static locked-off tripod, fixed frame | 固定机位，画面稳定不动 |
| 跟随 | Smooth follow-cam tracking, steady gimbal movement | Smooth gimbal tracking, floating camera | 镜头平滑跟随主体移动 |
| 环绕 | Slow orbital rotation around subject, 360° product view | Slow 180° orbit around product | 镜头环绕主体旋转，360度展示 |

### 4.6 Layer 4: STYLE — 风格/光影

**规则**：
- **单一强锚点 > 六个形容词堆砌**
- 光源方向必须明确（例: "soft window light from camera-right"）
- 色调使用具体颜色词（"warm amber tone" 而非 "暖色调"）

**光照预设**:

| 品类 | 主光源 | 辅光源 | 色调 |
|------|--------|--------|------|
| 食品饮料 | Warm natural sunlight, 45° left | Soft fill from front | Warm amber, appetizing |
| 美妆护肤 | Soft diffused beauty light, ring flash | Gentle rim light | Pearl white, clean |
| 电子3C | Cool blue accent rim light, dark studio | Subtle edge glow | Cool blue, premium |
| 服饰纺织 | Natural window light, soft shadows | Bounce fill | Neutral warm, natural |
| 家居厨具 | Warm kitchen light, practical | Soft overhead | Warm beige, homey |

**Seedance 专用风格词汇**:
```
商业广告: volumetric studio lighting, Arri Alexa 65, hyper-realistic 8k, masterpiece
自然清新: natural daylight, soft shadows, organic color palette, subtle film grain
高级质感: cinematic anamorphic lens, controlled reflections, subtle vignette, 35mm film look
食欲满满: warm vibrant colors, food photography lighting, visible steam particles, glossy highlights
科技未来: cool blue tones, clean minimal background, glass reflections, sci-fi product ambiance
```

### 4.7 Layer 5: CONSTRAINTS — 负向提示词

**规则**：只选 3-5 条最相关的，**全部堆砌会模糊画面**。

**通用禁止项**（所有平台共享）:
```
no text overlays, no watermarks, no logos
no warped objects, no melting edges
no extra fingers, no deformed hands
no jump cuts, no snap zooms
```

**平台专用禁止项**:

| 平台 | 专用禁止项 |
|------|-----------|
| Seedance | no whip pans, no Dutch angles, no neon lighting, no heavy teal/orange grade, keep product shape consistent, no morphing |
| Runway | stable lighting, no exposure flicker, single continuous shot, keep reflections clean, no refraction wobble, no speed ramps |
| Kling | 画面稳定不抖动，人物形象保持一致不变形，光线自然不要过度曝光，不要出现文字水印 |

### 4.8 提示词组装器

```python
class PromptAssembler:
    """按五层结构组装提示词"""

    def assemble(self, segment: FinalSegment, platform: str, product_type: str) -> PromptResult:
        # Layer 1: 主体
        subject = self.vocabulary.build_subject(
            product_type=product_type,
            product_name=segment.metadata.get("productName", ""),
            visual=segment.visual,
        )
        # Layer 2: 动作
        action = self.vocabulary.build_action(segment_type=segment.type, visual=segment.visual)
        # Layer 3: 镜头
        camera = self.vocabulary.build_camera(camera=segment.camera, platform=platform)
        # Layer 4: 风格
        style = self.vocabulary.build_style(product_type=product_type, emotion=segment.emotion, platform=platform)
        # Layer 5: 约束
        constraints = self.vocabulary.build_constraints(platform=platform, visual_fx=segment.visual_fx)

        return PromptResult(
            subject=subject, action=action, camera=camera,
            style=style, constraints=constraints,
            platform=platform,
        )
```

---

## 5. 平台适配器设计

### 5.1 SeedanceAdapter

**特点**: 中文+英文混合工作最佳，商业产品类优势明显，支持图文参考。

**输出格式**:
```
竖屏短视频画面，9:16构图：{品类前缀}，电商带货风格。
{主体描述}，{动作描述}。
镜头语言：{Seedance运镜英文词汇}。
光影风格：{volumetric studio lighting + 风格词}。
后期处理：{visual_fx 英文词汇}。
--ar 9:16 --style raw
```

**示例 — 食品饮料（旺仔牛奶）**:
```
竖屏短视频画面，9:16构图：食品饮料类，电商带货风格。
一瓶旺仔牛奶红色铁罐特写，光滑金属表面微微反光，红色包装上旺仔卡通形象清晰可见。
罐体在纯白背景前缓缓旋转展示，罐身凝结着细密水珠。
镜头语言：Cinematic high-end slow push-in tracking shot，微距拍摄，浅景深。
光影风格：Soft key light from 45° left，volumetric studio lighting，食品广告质感。
后期处理：Clean photorealistic render，no post effects。
--ar 9:16 --style raw
```

### 5.2 RunwayAdapter

**特点**: 纯英文，15-30词最佳，电影术语，产品一致性需参考图。

**输出格式**:
```
{Camera move}: {Subject description}. {Action}. {Lighting and environment}. {Mood and lens}.
```

**示例 — 食品饮料**:
```
Slow dolly-in: Close-up of a red Wangzai milk can, metallic surface with condensation droplets,
slowly rotating on a white pedestal. Soft studio key light from 45-degree left, gentle rim light 
creating subtle edge glow. Product commercial aesthetic, minimal clean white background, 
50mm macro lens, shallow depth of field. 5-second commercial shot.
```

### 5.3 KlingAdapter

**特点**: 中文情感驱动，重氛围和情绪，人物/角色一致性较好。

**输出格式**:
```
{氛围前缀}。{主体描述}，{动作描述}。{镜头描述}，{光影氛围}。{风格基调}。
```

**示例 — 食品饮料**:
```
温馨治愈的食品广告画面。一瓶红色旺仔牛奶铁罐，光滑表面凝结着细密水珠，
在纯白色背景前缓缓旋转展示。镜头慢慢推进，聚焦在罐身卡通形象上，浅景深效果。
柔和的工作室光线从左侧打来，产品边缘有一圈淡淡的高光。
整体色调温暖明快，让人产生食欲和怀旧感。
```

---

## 6. 品类自适应词汇系统

### 6.1 文件: `ai-services/services/prompt_engine/vocabulary.py`

### 6.2 品类→视觉词汇映射

```python
PRODUCT_VOCABULARY = {
    "食品饮料": {
        "液体类": {
            "subjects": ["beverage", "drink", "liquid", "bottle", "glass", "can"],
            "actions": ["pouring", "swirling", "bubbling", "steaming", "dripping"],
            "textures": ["glossy", "sparkling", "golden", "crystal-clear", "foamy"],
            "lighting": "warm natural sunlight, shallow depth of field, appetizing color grade",
        },
        "零食类": {
            "subjects": ["snack", "chips", "sticks", "bites", "pieces"],
            "actions": ["being picked up", "being bitten into", "scattered on surface"],
            "textures": ["crispy", "crunchy", "golden-brown", "flaky", "glazed"],
            "lighting": "warm vibrant colors, food photography lighting, glossy highlights",
        },
        "乳制品": {
            "subjects": ["milk", "yogurt", "cream", "cheese", "butter"],
            "actions": ["swirling in glass", "being poured", "being spread"],
            "textures": ["creamy", "smooth", "white", "fresh", "thick"],
            "lighting": "soft morning light, pure white background, clean aesthetic",
        },
    },
    "美妆护肤": {
        "膏体类": {
            "subjects": ["cream", "balm", "ointment", "paste"],
            "actions": ["being squeezed from tube", "being scooped", "being applied"],
            "textures": ["pearly", "velvety", "smooth", "rich", "whipped"],
            "lighting": "soft diffused beauty light, pearl-like reflections",
        },
        "液体类": {
            "subjects": ["serum", "essence", "toner", "oil", "liquid"],
            "actions": ["dripping from dropper", "spreading on surface", "being absorbed"],
            "textures": ["transparent", "golden", "viscous", "lightweight", "watery"],
            "lighting": "soft backlight, glass reflections, clean minimal background",
        },
    },
    "电子3C": {
        "手机/平板": {
            "subjects": ["smartphone", "tablet", "screen", "device"],
            "actions": ["screen lighting up", "being held", "being swiped"],
            "textures": ["metallic", "glossy", "edge-to-edge", "sleek", "premium"],
            "lighting": "cool blue accent rim light, dark reflective surface",
        },
        "耳机/音响": {
            "subjects": ["earbuds", "headphones", "speaker", "audio device"],
            "actions": ["floating in air", "being worn", "LED indicator pulsing"],
            "textures": ["matte", "brushed metal", "silicone", "premium", "compact"],
            "lighting": "dark studio, subtle edge glow, tech-inspired atmosphere",
        },
    },
}
```

### 6.3 情绪→运镜映射

```python
EMOTION_CAMERA_MAP = {
    "紧迫":   {"camera": "快推", "speed": "fast", "fx": "震屏"},
    "惊讶":   {"camera": "快推", "speed": "fast", "fx": "闪白"},
    "兴奋":   {"camera": "快推", "speed": "medium", "fx": "放大"},
    "亲切":   {"camera": "缓推", "speed": "slow", "fx": "无"},
    "权威":   {"camera": "静态", "speed": "static", "fx": "无"},
    "感动":   {"camera": "拉远", "speed": "slow", "fx": "慢动作"},
    "平静":   {"camera": "横移", "speed": "slow", "fx": "模糊过渡"},
}
```

---

## 7. 质量验证器

### 7.1 文件: `ai-services/services/prompt_engine/validator.py`

### 7.2 评分体系

每条 prompt 经过 7 项检查，满分 100 分。低于 70 分拒绝输出，触发重新生成。

```python
class PromptQualityValidator:
    MIN_SCORE = 70

    CHECKS = [
        ("length",           15,  "Prompt 长度在合理范围内（15-80词 Runway / 30-150词 Seedance）"),
        ("subject_position", 20,  "前30词包含明确的主体描述"),
        ("camera_present",   20,  "包含景别（CU/MS/ECU）或镜头运动（dolly/pan/track）"),
        ("style_present",    15,  "包含光照描述（key light/natural light/studio）或色调"),
        ("no_ambiguity",     10,  "无空洞形容词（漂亮/高级/好/很棒）"),
        ("negative_balance", 10,  "负向提示词3-5条，不多不少"),
        ("platform_valid",   10,  "符合目标平台的语法规范（Seedance用中文前缀/Runway纯英文/等）"),
    ]
```

### 7.3 验证结果

```python
@dataclass
class QualityReport:
    score: int          # 0-100
    passed: bool        # score >= MIN_SCORE
    feedback: list[str] # 未通过项的描述
    warnings: list[str] # 通过但可优化的项
```

---

## 8. 前端展示设计

### 8.1 VideoPlayer — 无视频时的提示词展示

当检测到分镜需要 AI 生成且 API 未配置时，视频播放器区域直接展示提示词列表：

```
┌─────────────────────────────────────────────────────┐
│  🟡 以下 5 个分镜可通过 AI 文生视频补齐             │
│  提示词已针对 Seedance 2.0 优化，可直接复制使用      │
│                                                      │
│  ┌─ Hook (3.0s) ────────────────── [📋 复制] ─────┐ │
│  │ 竖屏短视频画面，9:16构图：食品饮料类。           │ │
│  │ 旺仔牛奶红色铁罐特写，光滑金属表面反光...        │ │
│  │ 🎥 快推 | ✨ 震屏 | 🎬 $0.04                    │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Pain (4.0s) ────────────────── [📋 复制] ─────┐ │
│  │ ...                                              │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  [📋 一键复制全部 5 个提示词]                         │
│  [📥 导出为 Seedance JSON]  [📥 导出为 Runway TXT]   │
│  [🔑 配置 API Key 自动生成真实视频]                   │
└─────────────────────────────────────────────────────┘
```

### 8.2 ResultTimeline — AI 分镜标记

时间线上需要 AI 生成的分镜显示特殊视觉标记：

- **左侧色条**: 琥珀金 `#FFB300`
- **右上角标签**: `🤖 AI 待生成`
- **Hover 遮罩**: 显示提示词摘要（前60字符）
- **点击**: 打开 PayloadPreviewDrawer，定位到该分镜

### 8.3 PayloadPreviewDrawer — 导出功能增强

底部增加两个导出按钮：

```
[📋 导出全部提示词为 TXT]    [📋 导出为 Seedance JSON]
```

- **TXT 导出**: 按分镜顺序，每个分镜的提示词+字幕+参数，可直接复制到 Seedance/Runway/Kling
- **JSON 导出**: 完整的 API 请求体数组，可直接用于批量调用 Seedance API

---

## 9. 与现有系统的集成

### 9.1 零破坏兼容

| 现有文件 | 变更方式 | 影响 |
|---------|---------|------|
| `compositor.py` | `build_image_command` 调用改为 `ai_video_service.generate()` | 仅变更 AI 生成分支的代码路径 |
| `video_generator.py` | **保留**，Seedance API 调用函数不变 | 被 `ai_video_service` 内部调用 |
| `blueprint_renderer.py` | **保留**，重命名为 `prompt_card_renderer.py` | 无破坏 |
| `VideoPlayer.tsx` | 增强提示词展示区域 | 向后兼容 |
| `PayloadPreviewDrawer.tsx` | 增加导出按钮 | 向后兼容 |
| `ResultTimeline.tsx` | 增加 AI 分镜标记 | 向后兼容 |
| `migrator.py` | 无变更 | AI 生成在渲染阶段，不影响迁移 |

### 9.2 数据流变化

```
之前:
  FinalSegment(no asset) → compositor → try Seedance → fail → blueprint card → FFmpeg → video

之后:
  FinalSegment(no asset) → compositor → AIVideoService.generate()
    ├── [API configured] → Seedance API → real video → FFmpeg → video
    └── [API not configured] → PromptCard → prompt_card_renderer → FFmpeg → video
```

关键不变点：**音频链路完全不变**。TTS 配音和字幕照常工作，只是画面源从蓝图卡变成提示词卡。

---

## 10. 实施计划

### 10.1 文件清单

| 优先级 | 文件 | 类型 | 内容 |
|--------|------|------|------|
| **P0** | `ai-services/services/ai_video_service.py` | 新建 | AIVideoService + PromptCard + GeneratedVideo |
| **P0** | `ai-services/services/prompt_engine/__init__.py` | 新建 | 包初始化 |
| **P0** | `ai-services/services/prompt_engine/engine.py` | 新建 | AIVideoPromptEngine 主引擎 |
| **P0** | `ai-services/services/prompt_engine/assembler.py` | 新建 | PromptAssembler 五层结构组装 |
| **P0** | `ai-services/services/prompt_engine/vocabulary.py` | 新建 | 品类→词汇映射 + 情绪→运镜映射 |
| **P0** | `ai-services/services/prompt_engine/adapters/__init__.py` | 新建 | 适配器包 |
| **P0** | `ai-services/services/prompt_engine/adapters/seedance.py` | 新建 | Seedance 适配器 |
| **P0** | `ai-services/services/prompt_engine/negative_prompts.py` | 新建 | 三平台负向提示词库 |
| P1 | `ai-services/services/prompt_engine/validator.py` | 新建 | PromptQualityValidator |
| P1 | `ai-services/services/prompt_engine/adapters/runway.py` | 新建 | Runway 适配器 |
| P1 | `ai-services/services/prompt_engine/adapters/kling.py` | 新建 | Kling 适配器 |
| P1 | `ai-services/services/prompt_card_renderer.py` | 重命名 | 从 blueprint_renderer.py 演进 |
| P1 | `ai-services/services/compositor.py` | 修改 | 集成 AIVideoService |
| P1 | `src/components/result/VideoPlayer.tsx` | 修改 | 无视频时展示提示词列表 |
| P1 | `src/components/result/PayloadPreviewDrawer.tsx` | 修改 | 增加导出按钮 |
| P1 | `src/components/result/ResultTimeline.tsx` | 修改 | AI 分镜标记 |

### 10.2 预估工时

| 阶段 | 工时 | 交付物 |
|------|------|--------|
| P0 核心引擎 | 4-6 小时 | ai_video_service + prompt_engine 全部 + Seedance 适配器 |
| P1 扩展 + 集成 | 3-4 小时 | Runway/Kling 适配器 + compositor 集成 + 前端改动 |
| 测试验证 | 1-2 小时 | 单元测试 + 集成测试 |
| **总计** | **8-12 小时** | |

---

## 11. 答辩话术参考

### 11.1 "为什么是提示词卡片而不是直接生成视频？"

> "StructForge 的 AI 视频生成是一个独立服务层。当 API Key 配置后，系统自动调用 Seedance 生成真实视频。当 API 未配置时——比如现在这个 Demo 环境——系统不会报错，也不会假装有视频。它输出的是**可直接交付给下游渲染团队的专业提示词卡片**。您看到的每一张卡片都包含完整的多平台 prompt、制作参数、API payload 和成本预估。这意味着 StructForge 的产出不只是视频，还包括一份完整的 AI 生成调度文档，任何团队都可以拿去 Seedance、Runway 或 Kling 直接生成。"

### 11.2 "为什么提示词质量有保障？"

> "我们设计了一个五层结构化提示词引擎。它不像市面上大多数产品那样做简单的字符串拼接——它从分镜的品类、情绪、运镜参数出发，通过品类自适应词汇映射表选择最优词汇，经过 7 项质量检查（≥70分才输出），再根据目标平台（Seedance/Runway/Kling）的语法差异生成平台专用的 prompt。这不是"写一句话让 AI 猜"，而是工程化的、可验证的提示词生成系统。"

### 11.3 "为什么不直接接一个 API？"

> "这正是我们架构设计的关键决策。我们把 AI 视频生成做成独立服务层而非内嵌在渲染器里——这意味着底层模型是可替换的。今天用 Seedance，明天可以换成 Runway Gen-4 或 Kling 2.0，只需要写一个新的 Adapter。Prompt 结构不变，制作参数不变，成本预估自动更新。**这证明了 StructForge 的价值在上层的结构理解和调度编排，不在底层的某一个模型。**"

### 11.4 最终收尾

> "我的产品，连我自己都在用它来定义和创造爆款。您刚才看到的这条视频，就是 StructForge 从一条旺仔牛奶的抖音爆款中提取结构，迁移到新产品上，用我们自己的提示词引擎生成 AI 调度文档，最终渲染出来的。如果您给我一个 API Key，我可以当场把那些提示词卡片全部换成真实的 AI 生成画面。"
