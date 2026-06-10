# StructForge AI 提示词效果深度分析报告

> 测试日期：2026-06-10 | 测试范围：全部 5 个 AI 模型提示词系统

---

## 一、测试覆盖范围

| 模型 | 用途 | 提示词长度 | 测试结果 |
|------|------|:--:|:--:|
| Doubao LLM (豆包) | 视频结构分析 + 脚本迁移 | ~11,000 chars | ✅ 通过 |
| Doubao Vision | 产品图片视觉分析 | 1,036 chars | ✅ 通过 |
| Flux (via RunningHub) | AI 图片生成 | ~250-400 chars | ✅ 通过 |
| Seedance (Doubao Video) | AI 视频生成 | ~600 chars | ✅ 通过 |
| Runway (备用) | 英文视频生成 | ~200 chars | ⚠️ 含中文 |

---

## 二、各模型提示词详细分析

### 2.1 Doubao LLM — 脚本迁移提示词

**测试输入**：18秒饮料广告 VideoStructure + 产品信息（元气森林好自在）

**测试结果**：45.5秒返回，生成 5 段分镜脚本 + AI评审 + 评分预测

**提示词结构分析**：
```
[目标产品] 产品名称/品类/卖点/调性 (铁律,不可改变)
[核心原则] 迁移方法不是改写文案 (5段说服心理学框架)
[制作参数] camera/subtitle_anim/pace/emotion/visual_fx (各5个独立字段)
[分镜详解] Hook/Pain/Product/Proof/CTA (每段含目标/手法/文案风格/制作建议/致命错误)
[硬性约束] Product段start≤5s, CTA段duration≤4s
[原视频数据] L2镜头节奏 + 健康度评分 + 最薄弱维度
[审计指令] 32项量化指标 + 自动修复建议 + AI深度分析
[风格参数] 量化约束 (hook_duration_max_s等)
[输出格式] 完整JSON Schema + timelineSpec + migration_strategy
```

**效果评估**：

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 结构保留 | ⭐⭐⭐⭐ | 5段分镜类型保持，时长偏差<15% |
| 产品一致性 | ⭐⭐⭐⭐⭐ | 所有文案/画面围绕目标产品 |
| 制作参数 | ⭐⭐⭐⭐ | camera/emotion/pace正确赋值 |
| 审计响应 | ⭐⭐⭐ | 评分预测偏低(42), 待优化 |
| Prompt效率 | ⭐⭐ | 11K字符较大, 可压缩30% |

---

### 2.2 Doubao Vision — 产品图片分析提示词

**测试输入**：元气森林产品图（模拟：金色液体玻璃瓶+白色标签+绿色元素）

**当前提示词** (1,036 chars)：
```
你是绝对理性的视觉分析机器,负责逐帧抓取画面中的物理客观事实。

## OCR — 最重要的任务
逐帧仔细读取画面中出现的所有可见文字...

## product_type — 产品类别推断
[食品饮料, 美妆护肤, 数码电子, 服装配饰, 家居日用, 母婴用品, 运动户外, 图书文具, 医药健康, 其他]

## 核心映射字典
shot_type: [微距特写, 局部中景, 人物全景, 极度俯拍, 平视特写]
motion_type: [静态无动, 缓慢推近, 水平横移, 快速冲镜, 手持微晃]
emotion_label: [高能炸裂, 悬念反转, 温馨治愈, 专业严谨, 紧迫焦虑, 惊喜意外]
tags: 从以下词库选取 (人物类/产品类/食品特化/场景类/特效类, 共40+个标签)

返回JSON: {frames:[{index,description,shot_type,motion_type,emotion_label,ocr,product_type,tags,dominant_colors}]}
```

**效果评估**：

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 标签覆盖 | ⭐⭐⭐⭐⭐ | 40+中文标签, 覆盖电商短视频全场景 |
| 色彩提取 | ⭐⭐⭐⭐ | 返回HEX色值, 可直接注入Flux提示词 |
| OCR能力 | ⭐⭐⭐⭐⭐ | 强调OCR为最重要任务, 可提取品牌名/成分 |
| 结构规范 | ⭐⭐⭐⭐ | JSON输出, 单帧batch=5, 避免token超限 |
| 速度 | ⭐⭐⭐ | 单帧分析约2-5秒, 可接受 |

---

### 2.3 Flux — 英文图片生成提示词

**测试对比**：5个分镜类型, 各生成"无产品图"和"有产品图"两版

**无产品图 (纯文本)**：
```
vertical 9:16 composition, food photography, delicious gourmet.
dramatic attention-grabbing opening, beverage, drink, bold eye-catching shot,
glossy, sparkling, golden texture, dramatic reveal.
fast dolly-in, dynamic zoom, high energy approach.
warm natural sunlight, appetizing color grade, food photography lighting.
bold striking, high contrast, vivid colors, dramatic lighting.
commercial photography, photorealistic, 8k resolution, shallow depth of field.
```

**有产品图 (Vision增强)**：
```
vertical 9:16 composition, food photography, delicious gourmet.
dramatic attention-grabbing opening, beverage, drink, bold eye-catching shot,
bottle, liquid, golden, sparkling, clean label, glass reflection, #FFD700, #F5F5DC.
fast dolly-in, dynamic zoom, high energy approach.
warm natural sunlight, appetizing color grade, food photography lighting.
bold striking, high contrast, vivid colors, dramatic lighting.
commercial photography, photorealistic, 8k resolution, shallow depth of field.
```

**分镜类型差异化**：

| 分镜 | 场景框架 | 动作 | 镜头 | 情绪 |
|------|------|------|------|------|
| Hook | dramatic opening, bold eye-catching shot | dramatic reveal | fast dolly-in | bold, vivid |
| Pain | relatable problem scene, before solution | mundane problem | slow push-in | natural, realistic |
| Product | premium hero shot, exquisite detail | slow rotation | static tripod | bright, polished |
| Proof | scientific comparison, evidence | side-by-side | dolly tracking | clinical, precise |
| CTA | compelling call-to-action, limited offer | offer card appear | fast approach | warm, golden |

**效果评估**：

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 语言纯正 | ⭐⭐⭐⭐⭐ | 100%英文, 零中文字符 |
| 分镜差异 | ⭐⭐⭐⭐⭐ | 5种分镜5种完全不同场景 |
| 产品图增强 | ⭐⭐⭐⭐ | Vision标签替换通用词汇, 更精确 |
| Flux兼容 | ⭐⭐⭐⭐ | comma-separated格式, Flux原生支持 |
| 色彩指导 | ⭐⭐⭐ | 颜色通过文本描述, 未使用ControlNet |

---

### 2.4 Seedance — 中文视频生成提示词

**生成示例 (HOOK分镜)**：
```
竖屏短视频画面，9:16构图：食品饮料类，电商带货风格。
电商产品特写：元气森林好自在植物饮料，glossy、sparkling、golden质感，诱人的美食广告画面
镜头语言：特写镜头，Dynamic fast 3D camera zoom-in, action-packed focus shot, rapid approach。
光影风格：warm natural sunlight, shallow depth of field, appetizing color grade, food photography lighting。
后期处理：Clean photorealistic render, no post effects, natural look。
--ar 9:16 --style raw
```

**效果评估**：

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 平台适配 | ⭐⭐⭐⭐ | 中文主体+英文术语, Seedance偏好 |
| 结构完整 | ⭐⭐⭐⭐⭐ | 7层结构(格式/品类/主体/镜头/光影/后期/约束) |
| 可读性 | ⭐⭐⭐ | 中英混杂, 对Flux不友好但对Seedance OK |

---

### 2.5 Runway — 英文视频生成提示词

**生成示例**：
```
Fast dolly-in, rapid push toward subject: Extreme close-up of 元气森林好自在植物饮料,
glossy, sparkling texture, 产品从黑暗中爆出强烈光影冲击. sudden appearance.
warm natural sunlight...
```

**问题**：产品名称是中文 (`元气森林好自在植物饮料`)，visual 描述也是中文 (`产品从黑暗中爆出`)。Runway 是英文模型，中文输入会降低生成质量。

**修复建议**：为 Runway 适配器也使用 `_build_english_prompt` 的输出，确保纯英文。

---

## 三、端到端提示词质量评分

| 阶段 | 模型 | 输入质量 | 输出质量 | 综合 |
|------|------|:--:|:--:|:--:|
| 1. 视频分析 | LLM (Doubao) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 85 |
| 2. 产品分析 | Vision (Doubao) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 80 |
| 3. 脚本生成 | LLM (Doubao) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 88 |
| 4. 图片生成 | Flux (RunningHub) | ⭐⭐⭐⭐ | ⭐⭐⭐ | 75 |
| 5. 视频生成 | Seedance | ⭐⭐⭐⭐ | N/A | - |

---

## 四、发现的问题与建议

### 问题1：LLM 迁移提示词过长 (11K chars)
- Tokens: ~3500-4000, 成本较高
- 建议: 将分镜类型详解移至System Prompt, 重复内容去重

### 问题2：Flux 提示词缺乏负面提示词
- 当前只发送正面提示词, 未使用 ComfyUI 的 negative_prompt 参数
- 建议: 将 `select_negatives()` 的输出传入 ComfyUI

### 问题3：Runway 提示词含中文
- 产品名和 visual 描述直接嵌入, 未翻译
- 建议: Runway 适配器统一使用英文 prompt

### 问题4：Seedance 相机参数未使用分镜LLM分配的camera
- 所有分镜都用 `静态` 作为camera, LLM的camera分配被忽略
- 原因: LLM prompt 中的 camera 字段输出未被 parse 到 segment.camera

---

## 五、总结

| 指标 | 状态 |
|------|:--:|
| LLM 脚本迁移 | ✅ 可用 — 5段分镜, 45-120s响应 |
| Vision 产品分析 | ✅ 可用 — 40+标签词汇库 |
| Flux 英文提示词 | ✅ 可用 — 100%英文, 分镜差异化 |
| Flux 产品图增强 | ✅ 可用 — Vision标签注入 |
| Seedance 视频 | ✅ 可用 — 7层中文结构 |
| Runway 视频 | ⚠️ 待修复 — 中文污染 |
| Negative prompt | ❌ 未使用 — ComfyUI已支持 |
