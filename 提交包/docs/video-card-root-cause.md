# 视频仍为卡片形式的根因分析

## 问题现象

已配置全部 AI 模型（LLM / ASR / TTS / Seedream / Seedance），渲染输出仍是静态卡片。

## 根因追踪

追踪渲染链路，发现**四道闸门全部拦截**，AI视频生成代码从未真正执行：

---

### 闸门 1：Demo项目无真实视频源

**代码位置**：`seed.py`

```python
# seed.py 创建的 demo 项目
job_id = f"demo-job-{uuid4().hex[:8]}"
connection.execute(analysis_jobs.insert().values(
    job_id=job_id,
    source_path="",          # ← 空路径！没有真实视频文件
    ...
))
```

Demo 项目的 `source_path` 是空字符串。没有原始视频文件就无法创建 shot_pool（镜头池），视频重组和 AI 视频生成都拿不到输入素材。

**影响**：`_find_shot_for_segment()` 的 `shot_pool` 参数为 `[]`，直接返回 `None`。

---

### 闸门 2：渲染链路跳过 video generation

**代码位置**：`compositor.py` render() 渲染分镜循环

```python
# 当前逻辑：
if is_reference and segment.source != "reorder":
    shot_result = _find_shot_for_segment(...)    # 闸门1：shot_pool为空，返回None
    if shot_result:
        ...                                       # 永远不会到这里
    
    if not shot_used:                              # shot_used始终为False
        video_gen = VideoGenerator(...)
        if video_gen.available:
            ...                                    # 应该到这里！
```

VideoGenerator 应该被执行。但如果 `video_gen.available` 返回 `False`（API Key 未配置）或 `video_gen.generate()` 返回 `False`（API调用失败），就会掉到包装卡兜底。

**关键问题**：`VideoGenerator.__init__()` 检查 `self._available = bool(api_key)`。这里的 `api_key` 来自 `self.settings.doubao_image_api_key`。

---

### 闸门 3：VideoGenerator 可能静默失败

**代码位置**：`video_generator.py`

```python
class VideoGenerator:
    def __init__(self, api_key=None, model="..."):
        self._available = bool(api_key)    # ← 需要 doubao_image_api_key

    def generate(self, prompt, output_path, duration=5):
        # 两步式异步 API
        resp = httpx.post(CREATE_URL, ...)    # 可能因为以下原因失败：
        # 1. model 名称不正确 (doubao-seaweed-241128 vs doubao-seedance-xxx)
        # 2. API Key 权限不足（视频生成可能需要单独的权限开通）
        # 3. 账户余额不足（需要 ≥200 元）
        # 4. 网络超时（视频生成需要 10-120 秒）
        # 5. 返回状态不是 succeeded

        # 任何失败都 return False → 静默回退到卡片
```

**最可能的失败原因**：

1. **模型名称不匹配**：用户提供的模型名是 `doubao-seaweed-241128`，但 Seedance API 可能需要 `doubao-seedance-2-0-260128` 或类似的模型ID。模型名对不上 → API 返回 404。

2. **API Key 权限**：`doubao_image_api_key` 用于图片生成，可能没有开通视频生成权限。视频生成 API 可能需要单独的 Key 或在控制台单独开通。

3. **余额门槛**：Seedance 2.0 要求账户余额 ≥200 元。

---

### 闸门 4：静默回退无日志

**代码位置**：`compositor.py` + `video_generator.py`

所有 AI 路径的失败都是 `try/except: pass` 或 `return False`，没有任何日志输出。用户看不到：
- Shot pool 是否为空
- VideoGenerator 是否被调用
- API 返回了什么错误
- 为什么回退到卡片

**影响**：开发者无法排查问题，用户不知道原因。

---

## 根因总结

```
渲染一个分镜
  ├─ shot_pool 有数据？     → ❌ Demo项目source_path为空，无镜头池
  ├─ VideoGenerator 可用？   → ❓ API Key有但可能模型名/权限/余额不对
  ├─ Seedream 图片生成？     → ✅ 这个能工作（方形图）
  └─ 兜底：包装卡            → ← 你看到的输出
```

**三个根因**：

| # | 根因 | 严重度 |
|---|------|--------|
| 1 | Demo项目 source_path 为空，无法创建 shot_pool | 🔴 |
| 2 | VideoGenerator 静默失败，无日志 | 🔴 |
| 3 | Seedance 模型名/权限/余额 待验证 | 🔴 |

---

## 解决方案

### 修复 1：Demo 项目使用真实视频源

**文件**：`seed.py`

Demo 项目应该下载或生成一个真实的视频文件作为 source_path，这样 PySceneDetect 可以分析它创建 shot_pool，渲染时可以从中提取镜头。

实现方式：
- 用 FFmpeg 生成一段 30 秒的彩色测试视频（lavfi color source）
- source_path 指向这个文件
- 或者让 seed 项目跳过 reference 标记，让所有分镜直接走 AI 视频生成

### 修复 2：降级链路增加日志

**文件**：`compositor.py`, `video_generator.py`

每个降级步骤输出 warnings，让用户和开发者看到原因：
```
"shot_pool empty — trying AI video generation"
"VideoGenerator not available: API key not configured"
"VideoGenerator failed: HTTP 404 — model doubao-seaweed-241128 not found"
"Falling back to packaging card for segment seg-hook"
```

### 修复 3：验证 Seedance 连通性

**文件**：无代码改动，需要验证

用 curl 测试 Seedance API 是否通：
```bash
curl -X POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks \
  -H "Authorization: Bearer <IMAGE_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"doubao-seaweed-241128","content":[{"type":"text","text":"白色背景"}],"duration":4,"ratio":"9:16","resolution":"720p","watermark":false}'
```

如果返回 200 + task_id → 模型名正确，API Key 有权限
如果返回 404 → 模型名错误
如果返回 401/403 → Key 无权限或余额不足

### 修复 4：确保 seed 项目的 reference 正确绑定

**文件**：`seed.py`

当前 `create_demo_project` 创建了 job 但没有调用 `bind_reference_video_asset`。需要在 seed 中生成测试视频文件，设置 source_path，然后调用 bind。

---

## 建议执行顺序

```
1. 先用 curl 验证 Seedance API 连通性（30秒）
2. 确认模型名 → 更新 config.py（30秒） 
3. seed.py 生成测试视频 + 创建 shot_pool（30分钟）
4. compositor 增加降级日志（30分钟）
5. 测试：seed 项目渲染输出真实AI视频画面
```
