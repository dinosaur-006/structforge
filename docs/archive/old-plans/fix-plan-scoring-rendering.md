# StructForge 评分与渲染修复实施方案

> 日期: 2026-06-09  
> 状态: 待实施

---

## 修复清单

| # | 问题 | 根因 | 修复文件 | 优先级 |
|---|------|------|---------|--------|
| 1 | LLM 成功生成脚本后仍黑屏 | `_normalize_script` 默认 `source="original"`，compositor 走错分支 | `migrator.py` | 🔴 P0 |
| 2 | TTS 语速不匹配分镜时长导致截断 | `synthesize()` 固定 speed，不根据 target_duration 动态调整 | `compositor.py` + `tts_engine.py` | 🔴 P0 |
| 3 | compositor `shot_used` 未定义 | 变量只在视频分支声明 | `compositor.py`（已修复，需验证上线） | 🟡 P1 |

---

## 修复 1：`_normalize_script` 默认 source 修正

### 问题位置

`migrator.py` — `_normalize_script()` 中智能分镜映射和后续处理：

```python
# Line ~765: 智能映射中
seg.setdefault("source", "original")

# Line ~X: 后续处理中（如果存在）
seg.setdefault("source", "original")
```

### 根因

LLM 成功生成脚本时，不会在输出中包含 `source` 字段（Prompt 中没有要求）。`_normalize_script` 的 `setdefault` 将所有分镜默认设置为 `source="original"`。

compositor 看到 `source="original"` 且 `asset_id=None`，进入 no-asset 分支 → 走 AI 提示词卡片路径。**但 compositor 的 `shot_used = False` 声明在修复前不存在**，导致 AI 提示词代码静默失败 → 回退到 placeholder → 黑屏。

### 修复方案

**修改文件**: `ai-services/services/migrator.py`

**修改内容**: 在智能映射和后续处理中，根据分镜是否有用户素材来设置 source：

```
之前:
  seg.setdefault("source", "original")   # 全部默认 original

之后:
  # 有用户素材匹配的 → original，没有的 → aigc（走 AI 提示词卡片）
  src = "original" if seg.get("asset_id") and seg["asset_id"] in user_asset_ids else "aigc"
  seg.setdefault("source", src)
```

**需要的数据**: `user_asset_ids` — 排除参考视频后的用户素材 ID 列表。与 `_build_fallback_script` 中的逻辑一致。

### 影响范围

- 仅影响 LLM 成功路径（不走 fallback 时）
- 影响 `_normalize_script` 中的智能分镜映射段和后续迭代段
- 不影响已有用户素材的分镜

---

## 修复 2：TTS 语速动态调整

### 问题位置

`compositor.py:334`:
```python
tts.synthesize(full_script, full_tts_path, target_duration=total_dur)
```

`tts_engine.py` — `synthesize()` 方法使用固定 `speed` 参数。

### 根因

Volcano TTS API 的 `speed` 参数控制语速（正常=1.0，快点=1.2，慢点=0.8）。当前代码始终使用 `self.settings.tts_speed`（默认 1.0），不根据 `target_duration` 和文本长度计算所需速度。

当分镜总时长 42 秒但文案有 200+ 字时，1.0 速度下需要 50+ 秒才能读完 → 截断。

### 修复方案

**修改文件 1**: `ai-services/services/tts_engine.py`

在 `synthesize()` 方法中增加速度计算：

```
当前:
  speed = self.speed  # 固定值

修改后:
  if target_duration > 0 and text:
      # 中文朗读正常语速约 4-5 字/秒
      normal_duration = len(text) / 4.5
      required_speed = normal_duration / target_duration
      speed = min(max(required_speed, 0.8), 1.5)  # 限制在 0.8-1.5 之间
  else:
      speed = self.speed
```

- 正常语速基准：4.5 字/秒（中文朗读平均速度）
- speed < 1.0 表示需要加快（语音压缩）
- speed > 1.0 表示需要放慢（语音拉伸）
- 上下限 0.8-1.5 防止声音失真

**修改文件 2**: `ai-services/services/compositor.py`

将 `total_dur` 准确传递给 `synthesize()`。当前代码已经传了 `target_duration=total_dur`，无需修改。

### 备选方案（如果 API 不支持 speed 参数）

在 FFmpeg 中用 `atempo` 滤镜对合成后的 TTS 音频做变速：

```python
# 在 compositor 中，TTS 混入前
filter = f"[1:a]atempo={required_speed}[tts];[0:a][tts]amix=inputs=2:duration=first"
```

### 影响范围

- 仅影响 TTS 合成逻辑
- 不影响无声视频
- `atempo` 备选方案需要 FFmpeg 支持（>= 2.0）

---

## 修复 3：compositor `shot_used` 声明缺失（验证）

### 问题位置

`compositor.py:92` — `if source_path is None or not source_path.exists():`

### 状态

**已修复**。在 `source_path is None` 分支开头添加了 `shot_used = False` 声明。

### 验证方法

重启服务器后渲染视频，终端应输出：
```
[COMPOSITOR] No-asset path for seg-xxx (source=aigc, type=hook)
[COMPOSITOR] Prompt card generated for seg-xxx: XXXXX bytes
```

如果看到 `Falling back to placeholder`，说明 `render_blueprint_card` 执行失败，需要排查字体或图片生成问题。

---

## 实施顺序

```
Step 1: 修复 _normalize_script 的 source 默认值
        → 确保 LLM 成功路径的分镜也被标记为 aigc

Step 2: 修复 TTS 语速动态调整
        → 确保语音完整播放

Step 3: 重启服务器，重新走完整流程
        → 上传视频 → 分析 → 迁移 → 渲染
        → 验证: 终端输出 [COMPOSITOR] 日志
        → 验证: 视频中无素材分镜显示提示词卡片
        → 验证: TTS 配音完整播放不截断
```

---

## 验收标准

| 检查项 | 通过条件 |
|--------|---------|
| 视频无黑屏 | 所有无素材分镜显示提示词卡片（非纯黑画面） |
| TTS 不截断 | 每个分镜的配音完整播放到结束 |
| 终端日志 | 看到 `[COMPOSITOR] No-asset path` 和 `Prompt card generated` |
| 评分合理性 | baseline 与 generated 的得分差异来自实际文案改进，非随机数 |
| 来源类型正确 | 时间线 SmartLegend 显示 `🟠 AIGC 生成 (N)` 而非全部 `🟢 原素材` |
