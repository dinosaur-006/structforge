# WAN 2.2 视频生成失败根因分析

> 2026-06-10

---

## 一、错误信息

```
RunningHub task 2064649721091416066 failed: success
```

RunningHub API 返回 `status=FAILED, msg=success` — 任务在工作流平台上执行失败。

---

## 二、排查链

### 2.1 调用流程

```
我们的代码:
  comfyui_service.py L218-230
  params = {prompt, width:1080, height:1920, duration:3.0, image_path:"/tmp/test_flux_hook.png"}
  → kit.execute("1991693844100100097", params)

ComfyKit:
  runninghub_executor.py L103
  → 获取工作流定义 → "Workflow parsed successfully: 3 parameters found"
  → 创建任务 → Task created: 2064649721091416066
  → 轮询状态 → 37 秒后: status=FAILED, msg=success
```

### 2.2 参数不匹配问题

工作流定义只有 **3 个参数**，但我们发送了 **5 个**:

| 我们发送的 | 工作流是否需要 | 状态 |
|------|:--:|------|
| `prompt` | ✅ 必需 | 匹配 |
| `image_path` | ✅ 必需 (i2v) | 匹配 |
| `width` | ❓ 未知 | ⚠️ 可能不匹配 |
| `height` | ❓ 未知 | ⚠️ 可能不匹配 |
| `duration` | ❓ 未知 | ⚠️ 可能不匹配 |

ComfyKit 的 executor 会尝试将我们的参数映射到工作流的节点输入。如果参数名不匹配，该参数会被静默忽略。但如果关键参数（如 control image）映射失败，工作流会执行但产生空输出 → RunningHub 标记为 FAILED。

### 2.3 工作流 ID 验证

| 工作流 | ID | 状态 |
|------|------|:--:|
| image_flux | 1983427617984585729 | ✅ 已验证可用 |
| video_wan2.2 | 1991693844100100097 | ❌ 执行失败 |

这个 video_wan2.2 的 ID 来自 Pixelle-Video 项目，可能已经过期或参数格式不兼容。

### 2.4 图片格式

测试用的图片是从 CDN 下载的 PNG (1.9MB, 1080×1920)。格式应该兼容 WAN 2.2 的输入要求。

---

## 三、根因判断

**工作流参数映射失败** — 最可能的原因。ComfyUI 的 WAN 2.2 工作流在我们的参数名与工作流内部节点输入名不匹配，导致 image input 没有正确连接，工作流执行但产出空结果。

**次要可能**: 
- 工作流 ID 过期/无效
- RunningHub 平台的 WAN 2.2 工作流暂时不可用

---

## 四、修复方向

### 4.1 快速修复: 获取正确的参数名

需要在 RunningHub 平台上打开工作流 `1991693844100100097`，查看实际的节点输入参数名（可能是 `image`, `input_image`, `first_frame` 而不是 `image_path`）。

### 4.2 备选: 使用已验证的工作流

RunningHub 上有其他 WAN 2.2 工作流，可以尝试不同 ID 或重新上传已验证的 workflow JSON。

### 4.3 验证方法

```python
# 测试不同参数组合
params1 = {"prompt": "...", "image": img_path}           # 可能正确
params2 = {"prompt": "...", "input_image": img_path}     # 可能正确  
params3 = {"text": "...", "image_path": img_path}        # SDXL 风格
```

---

## 五、结论

视频生成失败是 **RunningHub 工作流配置问题**，不是代码逻辑 bug。Flux 图片生成（工作流 `1983427617984585729`）已验证完全可用。WAN 2.2 视频需要确认正确的参数映射后才能接入。
