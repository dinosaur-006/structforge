# StructForge 下一阶段优化实施方案

> 版本: 1.0  
> 日期: 2026-06-09  
> 状态: 分析完成，待实施

---

## 1. 问题全景图

过去几轮迭代中积累了若干需要修复的问题，按影响范围和依赖关系组织如下：

```
                    ┌──────────────────────────┐
                    │  P0: 素材上传入口缺失      │  ← 根因
                    │  AssetPanel 从未渲染       │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │ P1: 参考视频绑定 │ │ P2: AI 提示词 │ │ P3: 音频重叠      │
    │ 覆盖 AI 分镜     │ │ 卡片不可达    │ │ 原音轨+TTS 同时播放│
    └─────────────────┘ └──────────────┘ └──────────────────┘
              │                  │
              └────────┬─────────┘
                       ▼
            ┌──────────────────┐
            │ P4: LLM 迁移可靠性│
            │ auto-wrap/ID映射  │
            │ duration 自动修复  │
            └──────────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ P5: 渲染质量提升  │
            │ 震屏/BGM卡点/字幕 │
            └──────────────────┘
```

---

## 2. P0 — 素材上传入口（根因修复）

### 2.1 问题

`AssetPanel.tsx` 组件已完整实现（上传、缩略图、匹配状态、空态引导），但从未在任何页面渲染。`MigratePage.tsx` 没有引用它。

### 2.2 影响

用户无法上传产品图/视频，导致：
- 所有分镜 `assetId = None`
- `bind_reference_video_asset` 把参考视频绑定到所有分镜
- compositor 中 `source_path ≠ None`，跳过 AI 提示词卡片分支
- 最终渲染出黑屏或原视频片段

### 2.3 实施方案

| 步骤 | 文件 | 操作 |
|------|------|------|
| A | `src/pages/MigratePage.tsx` | 在侧边栏区域引入 `<AssetPanel>`，传入 `assets`/`assetLoading`/`onUploadAsset`/`projectId` |
| B | `src/pages/MigratePage.tsx` | 将现有的片段编辑区和 AssetPanel 并排（左右分栏或 Tabs 切换） |
| C | `src/store/index.ts` | 确认 `uploadAsset` action 在上传后自动调用 `matchAssets` + `listGaps` |
| D | `src/services/api.ts` | 确认 `analyzeAsset` 上传后返回 `asset_id` + `analysis` |

### 2.4 布局方案

```
┌─────────────────────────────────────────────────────────┐
│  编辑工作台                                    [生成脚本] │
├────────────────────────────┬────────────────────────────┤
│                            │  ┌─ 素材列表 ────────────┐ │
│   分镜编辑区                │  │  📤 拖拽或点击上传     │ │
│   (现有 SegmentBlock)       │  │                       │ │
│                            │  │  🖼 产品主图.png  92%  │ │
│                            │  │  🎬 使用场景.mp4  88%  │ │
│                            │  │  📝 卖点文案.txt  95%  │ │
│                            │  └──────────────────────┘ │
│                            │                            │
│                            │  ┌─ 缺口面板 ────────────┐ │
│                            │  │  🔴 Hook: 无素材       │ │
│                            │  │  🟢 Product: 已匹配    │ │
│                            │  │  🔴 CTA: 无素材        │ │
│                            │  └──────────────────────┘ │
└────────────────────────────┴────────────────────────────┘
```

---

## 3. P1 — 参考视频绑定逻辑修正

### 3.1 问题

`reference_assets.py:bind_reference_video_asset()` 中 `fill_unbound_only=True` 无法区分"用户没有上传素材"和"分镜本身需要 AI 生成"。当没有任何用户素材时，所有分镜 `assetId = None`，条件 `not segment.get("assetId")` 恒为 True，参考视频被绑定到所有分镜。

### 3.2 影响

compositor 中所有分镜都有参考视频作为 asset，走的是视频分支而非 AI 生成分支。AI 提示词卡片代码（`compositor.py` line 121-172）永不可达。

### 3.3 实施方案

| 步骤 | 文件 | 操作 |
|------|------|------|
| A | `reference_assets.py:47` | 增加判断：如果分镜 `source == "aigc"` 或 `source == "packaging"`，跳过绑定（这些分镜需要 AI 生成或包装补全，不适合用参考视频） |
| B | `compositor.py:210` | `is_reference` 检查后，对于 `segment.source == "aigc"` 的分镜，直接跳转到 AI 生成/提示词卡片路径，不进行 shot 重组 |
| C | `compositor.py:92` | 在 `source_path is None` 分支中已正确的 AI 提示词卡片逻辑无需改动，只需确保 reachable |

### 3.4 修复后的数据流

```
分镜 source="aigc", assetId=None:
  → reference_assets 跳过（source=aigc）         ← 修复点 A
  → compositor: source_path=None                ← 进入正确分支
  → AIVideoService.generate()                   ← 生成 PromptCard
  → render_blueprint_card()                     ← 渲染提示词卡片
  → FFmpeg → 视频显示提示词                      ← ✅ 用户看到提示词
```

---

## 4. P2 — 音频重叠修复

### 4.1 问题

原视频音频与 TTS 配音同时播放。已做过两次修复尝试，需要确认当前代码状态。

### 4.2 当前代码（已修复，需验证上线）

`compositor.py:344-351`:
```python
if is_reference:
    keep_audio = False              # 参考视频永远静音
else:
    keep_audio = (not bool(self.settings.tts_api_key)
                  and _has_audio_stream(...))
```

策略：
- 参考视频（原样例）→ **静音**
- 用户自有素材 + 无 TTS → 保留原音
- 用户自有素材 + 有 TTS → 静音（TTS 替代）

### 4.3 验证步骤

1. 确保服务器已加载最新 `compositor.py`
2. 渲染一条视频，检查音频是否重叠
3. 如果仍有重叠，在 `_run(command)` 前打印 `keep_audio` 值进行诊断

---

## 5. P3 — LLM 迁移可靠性增强

### 5.1 现状

已实现三层防御，LLM 返回单分镜或格式错误时自动修复：

| 层级 | 问题 | 修复 | 位置 |
|------|------|------|------|
| L1 | LLM 返回 `{id, type, ...}`（裸分镜） | `_try_wrap_flat_llm_output` 自动包装 | `schemas.py` |
| L2 | 包装后 `total_duration` 严重偏离（>50%） | 自动使用结构时长替换 | `migrator.py:730` |
| L3 | 分镜 ID 数量不匹配（1 vs 5） | 按位置映射到结构分镜 | `migrator.py:745` |

### 5.2 剩余风险

1. LLM 返回有效 FinalScript 但 segment count 完全对不上（如 3 个 vs 8 个）→ L3 只映射前 N 个，剩余的用模板填充 → 内容质量下降
2. `total_duration` 在 25%-50% 之间既不触发 L2 自动修复也不通过校验 → 需要调优阈值

### 5.3 优化方案（低优先级）

| 步骤 | 操作 |
|------|------|
| A | 监控 L3 触发频率。如果频繁触发（>30% 的生成都走 L3），说明 LLM prompt 中的 segment structure 描述不够清晰 |
| B | 增加 `_normalize_script` 的日志，记录每次 LLM 返回的 segment count vs 期望 count |
| C | 考虑在 prompt 中更显式地要求 "output exactly N segments with ids matching the structure" |

---

## 6. P4 — 渲染与视觉质量

### 6.1 震屏特效

- **现状**：`crop` 滤镜的 `sin()` 表达式与 FFmpeg 参数解析冲突，已降级为 `eq=contrast=1.25:brightness=0.06`
- **计划**：研究使用 `drawtext` 叠加帧偏移模拟震动，或使用 `geq` 滤镜实现逐帧位置偏移
- **优先级**：低（已有可用的对比度脉冲作为替代）

### 6.2 BGM 卡点对齐

- **现状**：已实现 `bgm.detect_beats()` 并在 compositor 中 snap segment start 到最近节拍（±0.15s）
- **验证**：需要实际渲染一条视频并人工确认卡点效果
- **优先级**：中

### 6.3 字幕动画

- **现状**：`subtitle_anim` 已连接到 ASS `\t` 变换标签（弹入/缩放/逐字）
- **验证**：需要渲染验证实际效果
- **优先级**：低

---

## 7. P5 — 前端体验完善

### 7.1 已完成的增强

| 功能 | 位置 | 状态 |
|------|------|------|
| Bento Box MetricCard | `MetricCard.tsx` | ✅ 已上线 |
| Pre-viz 全局指示器 | `AppLayout.tsx` | ✅ 已上线 |
| LLM 中断面板 | `LLMOutagePanel.tsx` | ✅ 已上线 |
| Payload 导出按钮 | `PayloadPreviewDrawer.tsx` | ✅ 已上线 |
| 提示词 TXT 导出 | `ResultPage.tsx` | ✅ 已上线 |
| SmartLegend（只显示在用类型） | `ResultTimeline.tsx` | ✅ 已上线 |

### 7.2 待完成

| 功能 | 说明 | 优先级 |
|------|------|--------|
| AssetPanel 接入 MigratePage | P0 核心修复 | 🔴 P0 |
| 一键渲染按钮状态联动 | `PayloadPreviewDrawer` 中「一键渲染」与 render status 联动 | 🟡 P2 |

---

## 8. 实施顺序

```
第 1 批（本次必须完成）:
  P0: AssetPanel 接入 MigratePage
  P1: reference_assets 绑定逻辑修正
  → 做完后 AI 提示词卡片可见，用户可上传素材

第 2 批（验证上线效果）:
  P2: 音频重叠 → 确认修复已生效
  P3: LLM 迁移 → 确认 L1/L2/L3 三层防御生效
  P6: 震屏/BGM/字幕 → 渲染验证

第 3 批（锦上添花）:
  P4: OverlayAdvisor + HighlightDetector 接入
  P5: 封面图前端展示
```

---

## 9. 验收标准

### 最小可行验收

1. 用户上传样例视频 → 分析完成 → 进入 MigratePage → **能看到素材上传区域**
2. 上传 1 张产品图 → **缺口面板中 Product 分镜状态变为"已匹配"**
3. 生成脚本 → 结果页 → 无素材的分镜**显示文生视频提示词卡片（非黑屏）**
4. 导出视频 → 播放 → **TTS 配音清晰，无原视频音频重叠**
5. 生成视频 → 重新上传到 StructForge → 审计 → **各维度得分不低于原视频 70%**

### 完整体验验收

以上全部 + ：
- BGM 卡点可感知
- 提示词 TXT 可导出
- Payload 抽屉可查看完整参数
- 分镜时间线颜色区分正确
- Pre-viz 指示器正常显示
