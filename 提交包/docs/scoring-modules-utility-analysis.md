# StructForge 评分模块效用分析

> 逐一评估每个评分/评估模块：哪些真正驱动 AI 决策，哪些只是展示用

---

## 总览

| 模块 | 驱动 AI? | 驱动渲染? | 仅展示? | 综合效用 |
|------|:--:|:--:|:--:|:--:|
| BurstAudit → LLM Prompt | ✅ | ❌ | ❌ | ⭐⭐⭐⭐⭐ 核心 |
| VideoStructure.health | ✅ | ❌ | ❌ | ⭐⭐⭐⭐⭐ 核心 |
| GapDetector | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ 核心 |
| AssetMatcher | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ 核心 |
| ResultEvaluator.baseline | ✅ | ❌ | ✅ | ⭐⭐⭐ 中等 |
| Predicted Scores (新增) | ❌ | ❌ | ✅ | ⭐⭐ 参考 |
| BurstMetricsCalculator 全量 | ❌ | ❌ | ✅ | ⭐⭐ 展示 |
| Self-Audit | ❌ | ❌ | ✅ | ⭐ 仅存储 |
| AIReview (qualitative) | ❌ | ❌ | ✅ | ⭐ 展示 |
| BurstAuditor LLM软分析 | ❌ | ❌ | ✅ | ⭐ 展示 |

---

## 逐一详细分析

### 1. BurstAudit → LLM Prompt — ⭐⭐⭐⭐⭐ 核心驱动

**位置**: `migrator.py` → `_build_audit_summary()` → `_build_prompt()`

**实际作用**:
```python
# 在迁移 prompt 中注入:
audit_context = {
    "weakest_dimensions": [
        {"dimension": "cta_persuasiveness", "score": 55, "weakness": "CTA缺少具体行动指令"}
    ],
    "auto_fix_suggestions": [
        {"target": "cta_persuasiveness", "action": "增加限时/限量/具体数字+明确点击指令"}
    ],
    "overall_rule_score": 64
}
```

**LLM 如何使用**: prompt 中写明 "你必须重点强化这些薄弱维度"，LLM 会根据这个数据针对性优化 CTA 段文案。

**是否有用**: ✅ **最有用**。这是唯一直接告诉 LLM "哪里该改" 的数据。没有它，LLM 只能凭直觉优化。

**改进空间**: 当前只传了 weakest_dimensions 和 auto_fix_suggestions。可以增加具体指标明细（如 "C-A1行动动词=0分，需增加'点击/抢/下单'"），让 LLM 知道具体缺什么词。

---

### 2. VideoStructure.health — ⭐⭐⭐⭐⭐ 核心驱动

**位置**: `migrator.py` → `original_scores` → `_build_prompt()`

**实际作用**:
```python
original_scores = {
    "hook_strength": 65,
    "product_exposure_timing": 58,
    "selling_point_proof": 72,
    "pacing_compactness": 70,
    "cta_persuasiveness": 55,
    "overall": 64,
    "weakest_dimensions": ["cta_persuasiveness(转化号召力)", "product_exposure_timing(产品露出时机)"]
}
```

**LLM 如何使用**: prompt 中展示 "原视频评分" 段落，LLM 被要求 "如果某项得分低于60，必须在该维度给出明显更强的方案"。这直接驱动 LLM 在 CTA 和产品露出两个维度加强。

**是否有用**: ✅ **必备**。没有这个基线对比，LLM 不知道参考视频的弱点在哪里。

---

### 3. GapDetector — ⭐⭐⭐⭐⭐ 核心驱动

**位置**: `migrator.py` → `gaps` → 传入 prompt context

**实际作用**:
```python
gaps = [
    {"id": "gap-2", "segmentId": "2", "type": "hook",
     "recommended_strategy": "aigc",
     "available_strategies": [{"id": "aigc", "name": "AIGC 生成", "available": True}, ...]}
]
```

**LLM 如何使用**: LLM 看到 gaps 数据，知道哪些分镜缺少素材，应该在 asset_id 中设为 null 并标记为 aigc 来源。

**渲染如何使用**: `_process_segments` 根据 segment.source 决定走 AI 生图还是用户素材路径。

**是否有用**: ✅ **必备**。素材缺口识别是赛题 P0 核心能力（20分）。

---

### 4. AssetMatcher — ⭐⭐⭐⭐⭐ 核心驱动

**位置**: `migrator.py` → `_normalize_script()` → 强制覆写 segment.source

**实际作用**:
```python
# 强制覆写:
aid = segment.get("asset_id")
segment["source"] = "original" if (aid and aid in user_asset_ids) else "aigc"
```

**渲染如何使用**: 决定渲染时走参考视频裁剪还是 AI 生图路径。

**是否有用**: ✅ **必备**。直接影响最终视频的每个分镜是用原素材还是 AI 生成。

---

### 5. ResultEvaluator.baseline — ⭐⭐⭐ 中等

**位置**: `migrator.py` → `evaluate_baseline(structure)` → 用于 qualitative_review 和前端展示

**实际作用**:
- 提供给 qualitative_review 的 before_scores（LLM 评审用）
- 前端展示 "规则量化得分" 和版本对比

**是否有用**: 🟡 **部分有用**。qualitative_review 的 LLM 评审是真正的 AI 驱动分析，但基线评分本身的数值只用于前端展示。去掉它不影响生成质量。

---

### 6. Predicted Scores (新增) — ⭐⭐ 参考

**位置**: `migrator.py` → 对生成的 FinalScript 做 BurstMetrics 评分 → 存入 metadata

**实际作用**: 前端展示 "脚本质量评估" 的 delta 对比。

**是否有用**: 🟡 **仅参考**。这个评分不驱动任何下游流程（不传给 LLM、不影响渲染）。纯粹是为了让用户看到 "AI 确实有提升"。

**改进**: 可以将 predicted_scores 的 weakest dimensions 反馈给用户，作为进一步 NL 编辑的参考。

---

### 7. BurstMetricsCalculator 全量 41 项 — ⭐⭐ 展示

**位置**: `burst_metrics.py` → `calculate_all()` + `dimension_reports()`

**实际下场**:
- `_build_audit_summary()` 只用了 weakest 和 suggestions（提炼后的摘要）
- BurstAuditPanel 前端展示（但用户看到的是参考视频的分，不是生成后的分）
- 自审计中用于快速评估

**是否有用**: 🟡 **大部分浪费**。41 项指标中，真正流入 LLM prompt 的只有 2-3 条摘要。H-V3 "画面亮度突变"、P-A1 "BGM情绪起伏" 等指标计算了但从未被使用。

**改进**: 要么删掉不用指标，要么让它们流入 LLM prompt。

---

### 8. Self-Audit — ⭐ 仅存储

**位置**: `render_pipeline.py` → `_finalize()`

**实际作用**: 渲染完成后评估生成视频，存入 `script.metadata.self_audit`。前端不可见。

**是否有用**: 🟡 **当前浪费**。已经计算了 visual_generation 质量（Flux/PromptCard）、flux_segments 数量等有价值的信息，但前端不展示。

**改进**: 至少把 visual_generation.method 和 flux_segments 数量展示给用户。

---

### 9. AIReview (qualitative) — ⭐ 展示

**位置**: `result_evaluator.py` → `qualitative_review()` → LLM 评审

**实际作用**: 调用 LLM 对新脚本做定性评审，输出改进建议。前端 `AIReview` 组件展示。

**是否有用**: 🟡 **当前浪费**。LLM 评审的内容很有价值（"Hook更尖锐，CTA更具体"），但仅供阅读，不驱动任何自动化流程。

**改进**: 可以将 AIReview 的 suggestions 反馈给 NL 编辑模块，让用户一键采纳建议。

---

### 10. BurstAuditor LLM 软分析 — ⭐ 展示

**位置**: `burst_auditor.py` → 调用 LLM 做软分析

**实际作用**: 分析参考视频的爆款特征、短板、改进建议。结果存入 FullAuditReport。

**是否有用**: 🟡 **当前浪费**。这个 LLM 调用消耗 token，但输出的 top_strength/top_weakness/suggestions 只展示在前端，不驱动任何下游流程。甚至没有传给迁移 LLM。

**改进**: 将 burst_auditor 的 suggestions 传入迁移 prompt（目前只有 rule-based 的 weakest_dimensions 传了，LLM 的 insights 没传）。

---

## 总结矩阵

```
作用层级:
  ⭐⭐⭐⭐⭐  直接驱动LLM迁移或渲染决策  →  GapDetector / AssetMatcher / health scores / audit summary
  ⭐⭐⭐     驱动LLM评审但非必要        →  ResultEvaluator.baseline
  ⭐⭐       提供用户参考               →  Predicted Scores / full 41 metrics
  ⭐         仅存储或仅展示             →  Self-Audit / AIReview / BurstAuditor LLM

实际流入 LLM prompt 的数据:
  1. product_identity (产品名/品类/卖点/语气)         ← 用户输入
  2. slim_structure (分镜骨架)                        ← 分析阶段
  3. original_scores (5维健康分)                      ← VideoStructure.health
  4. audit.weakest_dimensions + auto_fix_suggestions  ← BurstMetrics 摘要
  5. style_instruction + style_params                  ← 风格选择
  6. gaps + assets                                     ← 缺口检测 + 素材匹配
  7. shot_count + avg_shot_duration (新增)             ← L2 镜头节奏

被计算但未流入 LLM 的数据 (浪费的算力):
  1. 41 项 BurstMetrics 全量明细 (只用了摘要)
  2. BurstAuditor LLM 软分析结果 (完全未用)
  3. AIReview 评审建议 (仅供展示)
  4. Self-Audit visual_generation 质量报告 (仅供存储)
  5. Predicted Scores 全量 (仅供展示)
```

## 建议

### 立即可以砍掉的（不影响任何功能）

- BurstAuditPanel 中展示的 41 项全量明细 → 用户看不懂，也不驱动任何流程
- H-V3 "画面亮度突变" 等 10+ 个指标 → 计算了但从没被用过

### 应该接入 LLM prompt 的（花小力气提升大）

- BurstAuditor LLM 软分析的 suggestions → 传入迁移 prompt（目前浪费了 LLM token）
- AIReview 的改进建议 → 作为 NL 编辑的快捷选项（"一键采纳 AI 建议"）

### 应该展示的（当前隐藏了）

- Self-Audit 的 visual_generation 和 audio_generation → 让用户知道视频用了 Flux 还是 Prompt Card
- Predicted Scores 的 weakest dimensions → 告诉用户下一步 NL 编辑应该改哪里
