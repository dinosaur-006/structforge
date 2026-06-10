# StructForge 死代码与数据断连清理方案

> 日期: 2026-06-10  
> 状态: 分析完成

---

## 处理原则

| 标签 | 含义 | 操作 |
|------|------|------|
| 🗑️ 删除 | 被替代/从未使用/无未来价值 | 直接删除文件 |
| 📦 保留 | 有未来价值但当前未接入 | 保留文件，加注释标记 `# TODO: wire into pipeline` |
| 🔗 连接 | 逻辑完整只需最后一步接入 | 写几行代码打通数据流 |

---

## 一、后端死模块（5个）

### 1. `video_generator.py` → 🗑️ 删除

**内容**: `VideoGenerator` 类 + `build_master_prompt()` + `_hsl_to_rgb()`

**为什么可以删**：
- `VideoGenerator.generate()` 已被 `AIVideoService.generate()` 完全替代
- `build_master_prompt()` 已被 `prompt_engine/adapters/seedance.py` 的 `SeedanceAdapter.build_prompt()` 替代
- compositor.py 已不再导入此模块
- `generate_blueprint_fallback()` 逻辑已迁移到 compositor 的 PromptCard 渲染分支

**删除影响**: 零。无任何模块导入此文件。

**需确认**: 删除前 `grep -r "video_generator" ai-services/` 确认零引用。

### 2. `phase6_ai_gen.py` → 🗑️ 删除

**内容**: AI 视频生成的 Phase 6 实现（优化管线的一部分）

**为什么可以删**：
- `optimization_pipeline.py` 的 `run()` 方法中有 Phase 6 的占位逻辑，但从未实际调用此模块
- `AIVideoService` 已提供完整的 AI 视频生成能力
- Phase 6 中的 Seedance API 调用逻辑已被 `AIVideoService._call_seedance_api()` 覆盖

**删除影响**: 零。需同步删除 `optimization_pipeline.py` 中 Phase 6 的 log 占位行。

### 3. `phase2_subtitle.py` → 🗑️ 删除

**内容**: 基于 ASR 的字幕生成服务

**为什么可以删**：
- compositor.py 已通过 `_ass_for_segment()` 生成 ASS 字幕（从 FinalScript 的 script 字段）
- 当前字幕流程：`FinalSegment.script → _ass_for_segment() → FFmpeg subtitles filter`
- 此模块设计为从 ASR 片段生成字幕，但这个流程从未使用过
- 如果未来需要"从 ASR 生成字幕"（而非从脚本生成），可以重新实现

**删除影响**: 零。需同步删除 `optimization_pipeline.py` 中 `from services.phase2_subtitle import` 的引用。

### 4. `remotion_client.py` → 📦 保留

**内容**: Remotion 远程渲染的 HTTP 客户端

**为什么不删**：
- `RendererFactory` 已在 compositor 中使用 Remotion 模式
- 虽然 `remotion_client.py` 从未被直接导入，但它提供的 Remotion HTTP API 调用能力是 `RendererFactory` 的备选实现
- 当前 `RendererFactory` 使用 `renderer_abstraction.py` 调用 Remotion，两者功能重叠但实现不同

**处理**: 保留文件，在文件头添加注释：
```python
# NOTE: This module provides an alternative Remotion HTTP client.
# Currently unused — RendererFactory in renderer_abstraction.py handles
# Remotion calls. Keep for future direct Remotion integration.
```

### 5. `llm_presets.py` → 🗑️ 删除

**内容**: 预设的 LLM 模型配置列表

**为什么可以删**：
- `config.py` 已通过 `Settings` 管理 LLM 配置
- `llm_client.py` 从 Settings 读取 endpoint/model/key
- 此文件的预设列表（模型名/价格/上下文长度）从未被任何模块读取

**删除影响**: 零。

---

## 二、前端死组件（2个）

### 6. `DraftSegmentBlock.tsx` → 🗑️ 删除

**内容**: Pre-viz 蓝图草稿分镜块组件

**为什么可以删**：
- 为 MigratePage 时间线设计，但 MigratePage 使用的是 `SegmentBlock.tsx`（拖拽排序组件）
- ResultPage 的 `ResultTimeline.tsx` 有自己的内联 `SegmentBlock`，直接处理 draft 状态
- 组件功能已完全被现有代码覆盖

**删除影响**: 零。`DraftSegmentBlock` 从未被任何页面或组件导入。

### 7. `GeneratingPlaceholder.tsx` → 🗑️ 删除

**内容**: 视频生成中的占位动画组件

**为什么可以删**：
- `ExportDialog.tsx` 有自己的渲染进度展示
- `VideoPlayer.tsx` 有内置的渲染中状态（`isRendering` prop）
- 此组件设计为独立的全屏占位，但从未在任何页面渲染

**删除影响**: 零。无任何导入引用。

---

## 三、数据断连（3处）

### 8. `highlight_detector` → `compositor` → 📦 保留（P2）

**断连描述**: `HighlightDetector` 检测视频中的高光时刻（情绪峰值、视觉冲击点），但 compositor 从未使用这些高光标记来调整剪辑节奏。

**为什么暂不连接**：
- 高光检测需要 ASR 数据 + Vision 标签 + 情绪评分，这些数据在 compositor 渲染时已不完整（compositor 只拿到 FinalScript）
- 要连接需要：在迁移阶段运行高光检测 → 结果写入 FinalScript metadata → compositor 读取 → 在高光点加速节奏/加特效
- 工时 2-3h，影响中等

**处理**: 保留 `highlight_detector.py`，在文件头添加注释标记 P2 任务。

### 9. `overlay_advisor` → `compositor` → 📦 保留（P2）

**断连描述**: `OverlayAdvisor` 推荐贴纸/强调元素（价格标、倒计时、标签等），但 compositor 从未应用这些推荐。

**为什么暂不连接**：
- compositor 已有动画叠加层（Phase 7: `_apply_overlays`），使用 Remotion/Pillow 生成 CTA/Hook 动画
- OverlayAdvisor 的推荐更细粒度（每个分镜具体贴纸类型），需要新的 FFmpeg overlay 逻辑
- 当前 migrator 已调用 overlay_advisor 生成推荐，只需要 compositor 读取 `segment.metadata.overlay_recommendations`

**处理**: 保留，标记 P2。连接方式：compositor 从 segment metadata 读取 `overlay_recommendations` → 在 `_apply_overlays` 中生成对应贴纸。

### 10. `scene_classifier` → `asset_matcher` → 🔗 可连接（P1, 1h）

**断连描述**: `SceneClassifier` 将用户上传的素材分类为 hook/pain/product/proof/cta 五种场景类型，但 `AssetMatcher` 在匹配素材到分镜时未使用场景分类结果。

**为什么应该连接**：
- AssetMatcher 当前匹配基于关键词（tag matching），准确率有限
- SceneClassifier 已经对每个素材做了 LLM 分类，结果精确
- 连接成本极低：在 AssetMatcher 的 `_match_score` 中增加场景类型匹配加分

**连接方案**:
```python
# asset_matcher.py 中
def _match_score(self, asset, segment):
    score = 0
    # ... 现有关键词匹配 ...
    
    # NEW: scene type boost
    asset_scene = (asset.get("analysis") or {}).get("scene_type", "")
    if asset_scene == segment.type:
        score += 25  # 直接类型匹配 → 显著加分
    return min(score, 100)
```

**工时**: 1h。数据已存在，只需加判断逻辑。

---

## 四、清理执行清单

| # | 操作 | 文件 | 工时 |
|---|------|------|------|
| 1 | 🗑️ 删除 | `ai-services/services/video_generator.py` | 1min |
| 2 | 🗑️ 删除 | `ai-services/services/phase6_ai_gen.py` | 1min |
| 3 | 🗑️ 删除 | `ai-services/services/phase2_subtitle.py` | 1min |
| 4 | 📦 保留标记 | `ai-services/services/remotion_client.py` | 1min |
| 5 | 🗑️ 删除 | `ai-services/services/llm_presets.py` | 1min |
| 6 | 🗑️ 删除 | `src/components/migrate/DraftSegmentBlock.tsx` | 1min |
| 7 | 🗑️ 删除 | `src/components/result/GeneratingPlaceholder.tsx` | 1min |
| 8 | 🔗 连接 | `asset_matcher.py` (+scene_type boost) | 1h |
| 9 | 🧹 清理引用 | `optimization_pipeline.py` 中 Phase2/Phase6 引用 | 5min |
| 10 | 🧪 验证 | 全量测试确保删除不破坏现有功能 | 10min |

**总计: 约 1.5h**

---

## 五、删除影响评估

| 删除的文件 | 谁导入它 | 影响 |
|-----------|---------|------|
| `video_generator.py` | 无（上次已从 compositor 移除 import） | 零 |
| `phase6_ai_gen.py` | 仅 `optimization_pipeline.py`（需同步清理引用） | 需清理 2 行 import |
| `phase2_subtitle.py` | 仅 `optimization_pipeline.py`（需同步清理引用） | 需清理 2 行 import |
| `remotion_client.py` | 保留不删 | — |
| `llm_presets.py` | 无 | 零 |
| `DraftSegmentBlock.tsx` | 无 | 零 |
| `GeneratingPlaceholder.tsx` | 无 | 零 |
