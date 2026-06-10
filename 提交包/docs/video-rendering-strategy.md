# 视频渲染策略升级方案

## 问题定义

当前渲染结果中，没有用户素材的分镜渲染为静态 PNG 信息卡+配音。评审角度看，这不是"视频"，是幻灯片。

**目标**：无论用户有没有上传素材，输出都必须是真实动态视频——有画面运动、有视觉节奏、有视频感。

---

## 方案对比总览

| 方案 | 适用场景 | 画面质量 | 外部依赖 | 复杂度 | 推荐度 |
|------|---------|---------|---------|--------|--------|
| 方案1: 智能重组 | 有原始样例视频 | ⭐⭐⭐⭐⭐ 真实视频 | 无 | 中 | 🔥🔥🔥🔥🔥 |
| 方案2: AI视频生成 | 无任何素材 | ⭐⭐⭐ AI生成 | 即梦视频API | 高 | 🔥🔥🔥 |
| 方案3: 关键帧动画 | 兜底方案 | ⭐⭐⭐ 动态画面 | 无 | 低 | 🔥🔥🔥🔥 |
| 方案4: 模板动画 | 兜底方案 | ⭐⭐ 程序化 | 无 | 中 | 🔥🔥 |
| 方案5: 素材库 | 通用场景 | ⭐⭐⭐ 真实素材 | Pexels API | 中 | 🔥🔥🔥 |

---

## 方案1: 智能视频重组（推荐优先实施）

### 原理
将原始样例视频的所有镜头用 PySceneDetect 分割 → Vision 分析每个镜头的场景类型 → 按新的分镜脚本重新排列组装。

### 流程
```
原始样例视频 (30s)
    │
    ├─ PySceneDetect 检测所有镜头边界 → 12个镜头片段
    │
    ├─ 每个片段提取关键帧 → Vision 分析 → 标注类型(hook/pain/product/proof/cta)
    │
    ├─ 按新脚本的分镜需求，从标注池中选取最匹配的镜头
    │   - Hook分镜需要"冲突画面" → 选标签匹配的镜头
    │   - Product分镜需要"产品特写" → 选产品镜头
    │   - CTA分镜需要"购买引导" → 选价格/Logo镜头
    │
    ├─ FFmpeg 剪辑+重新拼接 → 新的视频片段
    │
    └─ 叠加新字幕 → concat 输出
```

### 关键技术点

1. **PySceneDetect 自适应阈值**
   - 当前阈值: 27.0（固定）
   - 优化: 根据视频内容动态调整——快节奏视频降低阈值(更多镜头)，慢节奏提高

2. **镜头池管理**
   - 每个被检测到的镜头存储: {start_ms, end_ms, vision_tags, scene_type, duration}
   - 支持一个镜头被多个分镜复用（裁切不同部位）
   - 支持镜头拉伸/压缩（慢放/快放）

3. **智能选镜算法**
   - 优先选择 scene_type 精确匹配的镜头
   - 其次选择 vision_tags 关键词匹配的镜头
   - 最后选择时长最接近的镜头
   - 如果镜头池不够 → 同一镜头可被裁切为多个片段使用

### 涉及的改动

| 文件 | 改动 |
|------|------|
| `services/media.py` | `detect_scenes()` 返回更细粒度的镜头信息 |
| `services/vision.py` | 为每个镜头分析场景类型 |
| `services/pipeline.py` | 分析时存储镜头池到 job result |
| `services/compositor.py` | 新增 `_render_from_shot_pool()` 方法 |
| `services/migrator.py` | 生成分镜时标注期望的镜头类型 |

### 预期效果
- 有真实视频画面（来自原始样例）
- 镜头重新排列，匹配新结构
- 画面流畅，视觉质量等同原始视频

---

## 方案2: AI 视频生成

### 原理
使用火山引擎即梦/Seedream 的视频生成能力，根据分镜的 visual 描述直接生成短视频片段。

### 两种子方案

**子方案 A: 图生视频（Image-to-Video）**
- 先用 Seedream 生成一帧关键画面（已有能力）
- 将关键帧+运动描述发给视频生成模型 → 生成2-5秒短视频
- 优势: 画面质量可控（先生成好图再生视频）
- 劣势: 需要两次API调用，成本较高

**子方案 B: 文生视频（Text-to-Video）**
- 直接将 visual 描述发给视频生成模型
- 优势: 一步到位
- 劣势: 画面质量可能不如图生视频

### API 端点（待确认）
```
POST https://ark.cn-beijing.volces.com/api/v3/video/generations
Authorization: Bearer <API_KEY>
{
  "model": "doubao-seedream-video-xxx",
  "prompt": "产品特写旋转展示，柔和工作室灯光，1080x1920竖屏",
  "duration": 3,
  "size": "1080x1920"
}
```

### 涉及的改动

| 文件 | 改动 |
|------|------|
| `config.py` | 新增 `doubao_video_model` + `doubao_video_api_key` |
| `services/` | 新建 `video_generator.py` |
| `services/compositor.py` | 调用 video_generator 替代静态卡片 |
| `services/gap_filler.py` | AIGC 策略增加视频生成选项 |

### 预期效果
- 完全由AI生成的短视频画面
- 每个分镜有独立动态画面
- 与文案/字幕完美配合

---

## 方案3: 关键帧动画增强（当前 Ken Burns 的升级版）

### 当前状态
已实现基础的 Ken Burns 缩放动画（zoompan 从 1.0x → 1.06x）。

### 升级内容
1. **多关键帧路径**: 不只缩放，增加水平/垂直平移
2. **变速运动**: 使用 ease-in-out 缓动曲线
3. **多图叠加**: 前景+背景分层动画
4. **文字动画**: 文案逐字弹入（用 FFmpeg drawtext 表达式）
5. **粒子/光效**: 简单的粒子或光线扫过效果

### FFmpeg 实现
```bash
# 复杂关键帧动画示例
zoompan=z='if(lte(t,1),1+0.02*t,if(lte(t,2),1.02,1.02+0.01*(t-2)))': \
  x='iw/2-(iw/zoom/2)+5*sin(t*0.5)': \  # 水平微摆
  y='ih/2-(ih/zoom/2)-3*t': \             # 缓慢上移
  d=1:s=1080x1920:fps=30
```

### 预期效果
- 静态卡片变成有呼吸感的动态画面
- 不需要外部API，纯FFmpeg实现
- 作为方案1和方案2的兜底

---

## 渲染决策树（最终逻辑）

```
渲染一个分镜
├─ 有用户上传的视频素材？
│   ├─ 是 → 使用用户视频片段（当前已实现）
│   └─ 否 → 继续判断
│
├─ 有原始样例视频的镜头池？
│   ├─ 是 → 方案1: 从镜头池选最佳匹配镜头
│   └─ 否 → 继续判断
│
├─ AI视频生成API可用？
│   ├─ 是 → 方案2: 调用API生成短视频
│   └─ 否 → 继续判断
│
├─ 有相关关键帧图片？
│   ├─ 是 → 方案3: 关键帧动画（Ken Burns增强版）
│   └─ 否 → 方案4: 程序化模板动画
```

---

## 实施建议

### Phase 1: 方案3 增强（1天）— 兜底质量提升
- 当前 Ken Burns 已实现
- 增加平移+缓动+多关键帧
- 效果：静态卡→动态画面

### Phase 2: 方案1 镜头池（2-3天）— 核心能力
- PySceneDetect 细粒度镜头分割
- Vision 镜头类型标注
- compositor 镜头池重组渲染
- 效果：有原始视频时输出真实重组视频

### Phase 3: 方案2 AI视频生成（1-2天）— 锦上添花
- 需要火山引擎开通视频生成API
- 实现 video_generator.py
- 效果：完全没有素材也能生成视频

### 不推荐
- 方案5（素材库集成）：版权风险+网络依赖
- 方案4（纯模板动画）：太像PPT

---

## 关键技术细节

### PySceneDetect 镜头池

```python
# 当前: 只返回镜头边界
scenes = [{"start_ms": 0, "end_ms": 3000, "duration_ms": 3000}]

# 升级: 每个镜头附带关键帧路径和Vision分析
scenes = [{
    "start_ms": 0, "end_ms": 3000,
    "keyframe_path": "/frames/frame_0001.jpg",
    "vision_tags": ["冲突画面", "产品特写"],
    "scene_type": "hook",
    "shot_style": "快推+特写",
    "reusable": True,
}]
```

### 镜头选取算法

```
输入: 目标分镜类型(hook/pain/product/proof/cta), 需要时长(duration)
输出: 最佳镜头片段 {shot_id, start_offset, clip_duration}

1. 精确匹配: scene_type == target_type → 直接用
2. 标签匹配: vision_tags 含对应关键词 → 候选
3. 时长匹配: 选时长最接近的镜头
4. 若不够: 同一镜头裁切多个片段
5. 若仍不够: 降级到方案3（关键帧动画）
```

### 视频重组渲染

```python
def render_from_shot_pool(segment, shot_pool):
    best_shot = select_best_shot(segment.type, segment.duration, shot_pool)
    if best_shot:
        # FFmpeg: 从原始视频裁剪 best_shot 时间段
        cmd = ["ffmpeg", "-ss", best_shot.start, "-i", original_video,
               "-t", segment.duration, "-c:v", "libx264", output]
    else:
        # 降级: Ken Burns 动画
        cmd = build_image_command(...)
```
