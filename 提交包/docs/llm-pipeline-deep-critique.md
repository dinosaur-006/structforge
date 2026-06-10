# StructForge LLM 管线深度批判分析

> 视角 A: 赛题评委（评分标准逐条对照）  
> 视角 B: 真实用户（从点击到满意的完整体验）  
> 不保留情面，找出所有问题

---

## 一、评委视角：对照评分标准的问题

### 1.1 结构拆解（10分）— 当前 ~7/10

**问题 1: L2 镜头节奏结构未传递**

分析阶段已计算 `shot_count` 和 `avg_shot_duration`（P0.2 新增），但 `_build_prompt()` 的 `slim_structure` 中**没有把这两个字段放进去**：

```python
slim_structure = {
    "script": [
        {"id": s.id, "type": s.type, "label": s.label,
         "start": s.start, "end": s.end, "duration": s.duration,
         "goal": s.goal, "copy": s.copy_text, "visual": s.visual,
         "healthScore": s.healthScore,
         # ❌ 缺少 shot_count, avg_shot_duration
        }
    ]
}
```

LLM 看不到参考视频的镜头节奏数据，就无法在迁移时保留或优化节奏模式。评审看到"你提取了 3 类结构信息"，但实际只传递了 L1 脚本结构，**L2 镜头节奏虽然在分析阶段计算了，但被丢弃了**。

**问题 2: 包装结构传递不完整**

`packaging` 字段传了全量数据，但 LLM prompt 中对包装结构的利用没有明确指导。LLM 不知道"subtitleDensity: high"意味着 "每段至少 1 条字幕，Hook 段需 2 条以上"。

**改进**: 在 prompt 中增加一段明确的结构传递说明，让 LLM 知道自己应该保留什么、优化什么。

### 1.2 结构迁移生成（10分）— 当前 ~9/10

**问题 3: 迁移过程不可解释**

这是一个致命的设计问题。LLM 一次性输出 FinalScript，中间没有任何可追溯的推理步骤。评委问"这个 Hook 的 visual_fx 为什么是震屏？"，答案是"LLM 决定的"——这不是好的可解释性。

理想流程应该是：
```
① LLM 分析参考结构 → 识别关键模式
② LLM 规划迁移策略 → 说明保留什么/改变什么  
③ LLM 生成新脚本 → 标注每个决策的理由
④ 前端展示 ①→②→③ 的完整推理链
```

当前只有 ③，缺失 ① 和 ②。这对赛题"迁移过程可视化"评分项（10分）有直接影响。

**改进**: 将 prompt 拆分为两阶段调用——先让 LLM 输出迁移策略（保留L1结构、优化L2节奏、替换L3包装文案），再基于策略生成脚本。策略本身作为可展示的中间产物。

### 1.3 素材缺口识别（8分）— 当前 ~3/10 → 修复后 ~7/10

**问题 4: 缺口检测逻辑未反馈给 LLM**

`gaps` 数据传入了 prompt context JSON，但 prompt 文本中没有明确指令告诉 LLM **如何使用缺口数据**。LLM 看到 gaps 数组，但不知道该优先分配 asset_id 还是标记为 aigc。

当前 `_normalize_script` 在 LLM 返回后才做素材匹配修正——这是事后补救，不是事前规划。

### 1.4 人工可调能力（8分）— 当前 ~7/10

**问题 5: NL 编辑不是真正的"对话式调整"**

当前 NL 编辑是对 VideoStructure 做 JSON Patch，而不是对 FinalScript。用户输入"把商品信息提前"，修改的是分析阶段的结构，然后需要重新生成脚本才能看到效果。这不是"改片"而是"改结构再生成"。

评委期待的是：用户对已生成的脚本说"开头更抓人一些"，系统能直接修改 FinalScript 的 Hook 段文案和制作参数，而不需要重新调用 LLM 迁移。

### 1.5 多样例融合（加分项）— 当前 0/加分

**问题 6: 完全不支持多样例**

`_build_prompt` 只接受一个 `structure` 对象。即使 AnalyzePage 支持多样例上传，migrator 也只能用其中一条作为参考。没有"从两条爆款视频中分别提取 Hook 策略和 CTA 策略，融合为最优方案"的能力。

---

## 二、用户视角：从点击到满意的体验问题

### 2.1 输入阶段

**问题 7: 产品信息质量无保障**

用户输入"超好吃"作为卖点——这太模糊了。LLM 被迫从 3 个字推测整个产品的视觉特征、使用场景、目标人群。结果质量完全取决于用户输入质量，而系统不做任何引导或丰富。

**问题 8: 用户不知道 LLM 会怎么理解他们的输入**

没有"预览我的产品会被 AI 理解成什么"的环节。用户可能以为"奥利奥薄脆"会被描述为"饼干"，但 LLM 可能基于训练数据中的关联，将其描述为"童年怀旧零食"——方向完全不同。

**问题 9: 风格选择没有预览**

用户选择"高点击"但不知道具体会改变什么。"高点击"的风格指令是"强化前三秒冲突和停留理由，Hook 文案更短、更尖锐"——但这个信息对用户隐藏。用户只能靠猜。

### 2.2 生成阶段

**问题 10: 等待期间的体验是空白**

点击"生成脚本"后，用户看到的是 `<Loader2>` 旋转图标 + "正在生成脚本…"。没有进度信息，没有中间产物展示。如果 LLM 超时（120s），用户不知道为什么失败。

**问题 11: 一次性输出的风险**

LLM 在 ~8000 token prompt 下一次性生成 11 段完整脚本。如果第 3 段 Hook 写得不好，整批作废。没有"先出大纲，确认后再写细节"的分步机制。

**问题 12: 没有"后悔"路径**

生成后如果不满意，只能 NL 编辑或换风格重新生成。没有版本对比、没有局部替换、没有"只重新生成 Pain 段"的选项。

### 2.3 审核阶段

**问题 13: ReviewPanel 只看不调**

用户可以在 ReviewPanel 看到每个分镜的 script/visual/camera/emotion，但不能直接编辑。只能通过 COPY SEEDANCE PROMPT 复制到外部工具修改。这和赛题"人工可调"的要求有差距——评委期待的是**在系统内完成调整 → 重新渲染受影响段落**。

**问题 14: 用户不理解 visual 和 prompt_text 的区别**

ReviewPanel 显示两个东西：`script`（口播文案）和 `visual`（画面描述）。但还有一个隐藏的 `prompt_text`（喂给 ComfyUI 的英文提示词）。用户看到中文 visual 描述，但 ComfyUI 用的是英文 prompt_text——两者的对应关系不透明。

---

## 三、Prompt 工程自身的 5 个问题

### 问题 15: 单体 Prompt 过于庞大

当前 prompt ~8000 tokens，包含：角色定义 + 产品约束 + 框架解释 + 参数枚举 + 分镜详解(5种×~100字) + 健康诊断 + 审计指令 + 品牌参数 + 风格指令 + JSON Schema + 硬性规则 + 完整上下文 JSON。

这导致：
- LLM 注意力分散——5 种分镜的详细指导都在同一个 prompt 里，LLM 可能混淆
- Token 成本高——每次生成消耗 ~10000 tokens
- 难以调试——不知道是哪部分导致 LLM 输出异常

### 问题 16: JSON Schema 和自然语言指令的冲突

Prompt 中说"保持样例的段落数和段落类型"，但 JSON Schema 中又有 `restructure_needed` 字段让 LLM 提出重排建议。LLM 夹在"保持结构"和"可以重排"的矛盾指令之间。

### 问题 17: 5 个制作参数的选取没有依据

`camera` 字段接受 7 个值。LLM 如何为 Hook 段选择"快推"而非"手持微晃"？当前全靠 LLM 的训练数据直觉。一个更稳健的设计是：基于分镜类型和 healthScore 给 LLM 明确的参数选择规则。

### 问题 18: 风格指令实现方式脆弱

```python
STYLE_INSTRUCTIONS = {
    "high_click": "强化前三秒冲突和停留理由，Hook 文案更短、更尖锐，字幕更醒目。",
    "high_conversion": "强化信任背书、优惠理由和 CTA 紧迫感...",
}
```

这 6 个风格的指令是自然语言描述，LLM 对"更短"、"更尖锐"、"更醒目"的理解是模糊的。更好的方式是用具体参数：high_click → hook.duration≤2s, hook.camera=快推, hook.visual_fx=震屏。

### 问题 19: 产品名提取的优先级不可见

`_extract_product_identity` 有 3 级优先级（brief > structure.meta > project name）。但当 brief.productName="奥利奥薄脆" 而 structure.meta.productName="旺仔牛奶"（参考视频的产品），哪个该优先？当前逻辑不透明，用户不知道系统到底用了哪个产品名。

---

## 四、优化建议优先级

### P0 — 必须修（影响赛题评分）

| # | 问题 | 改进 | 工时 |
|:--|------|------|:--:|
| 1 | **shot_count 未传递** | slim_structure 增加 shot_count/avg_shot_duration；prompt 增加"保留镜头节奏模式"指令 | 0.5h |
| 2 | **迁移不可解释** | 两阶段 prompt：先输出迁移策略，再基于策略生成脚本 | 2h |
| 3 | **风格指令可量化** | 枚举值改为具体参数映射（如 high_click→hook.dur≤2s, camera=快推） | 1h |

### P1 — 应该修（提升用户体验）

| # | 问题 | 改进 | 工时 |
|:--|------|------|:--:|
| 4 | **产品输入引导** | 输入框下方显示"AI 将如何理解你的产品"预览 | 1h |
| 5 | **生成进度可见** | SSE 推送 LLM 生成进度（"正在分析结构→规划迁移→生成分镜 3/11"） | 1h |
| 6 | **风格选择有描述** | 每个风格选项展开显示具体会改变什么 | 0.5h |
| 7 | **ReviewPanel 可编辑** | 分镜卡片增加内联编辑 script/visual | 2h |

### P2 — 锦上添花

| # | 问题 | 改进 | 工时 |
|:--|------|------|:--:|
| 8 | **多样例融合** | 支持 2-3 条参考视频的结构融合 | 3h |
| 9 | **局部重生成** | NL 编辑后只重新生成受影响的段落 | 2h |
| 10 | **版本对比** | 生成后并排展示旧版本 vs 新版本差异 | 1h |

---

## 五、P0 实施细节

### P0-1: shot_count 传递（0.5h）

```python
# migrator.py slim_structure 增加:
"script": [
    {
        "id": s.id, "type": s.type, ...
        "shot_count": s.shot_count,           # ← 新增
        "avg_shot_duration": s.avg_shot_duration,  # ← 新增
    }
]

# _build_prompt() 增加:
## 原视频镜头节奏（L2 结构）
原视频每段的镜头数和平均镜头时长如下。新脚本应保留快慢节奏的相对关系，
但在薄弱段落可适当增加镜头数提升节奏感。
（然后列出每段的 shot_count 和 avg_shot_duration）
```

### P0-2: 两阶段迁移（2h）

```
Stage 1 prompt（短，~500 tokens）:
  分析参考结构的 11 段分镜，输出 JSON 迁移策略:
  { "preserve": ["hook 2段开头模式", "product段在8s处露出"],
    "strengthen": ["cta段增强紧迫感", "product段提前到5s内"],
    "weaken": [],
    "strategy_brief": "保留原视频的快节奏Hook模式，将产品露出提前2秒..." }

Stage 2 prompt（基于策略）:
  根据以上迁移策略，生成完整的 11 段 FinalScript。
  （原 prompt 内容，但不需要重复"核心原则"，因为 Stage 1 已经分析了）
```

Stage 1 的输出本身就可以在 ReviewPanel 中展示为"AI 迁移策略"卡片，直接满足赛题"迁移过程可视化"要求。

### P0-3: 风格量化（1h）

```python
STYLE_PARAMS = {
    "high_click": {
        "hook_duration_max": 2.0,     # Hook不超过2秒
        "hook_camera": "快推",         # Hook强制快推
        "hook_emotion": "惊讶",        # Hook强制惊讶
        "subtitle_size": "larger",     # 字幕更大
        "overall_pace": "fast",
    },
    "high_conversion": {
        "cta_duration_max": 3.0,       # CTA不超过3秒
        "cta_emotion": "紧迫",         # CTA强制紧迫
        "proof_count_min": 3,          # 至少3段Proof
    },
    # ...
}
```

将这些量化参数直接注入 prompt，LLM 不需要"理解"风格，只需要"执行"参数。
