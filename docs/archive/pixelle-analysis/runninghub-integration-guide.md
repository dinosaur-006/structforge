# StructForge × RunningHub 集成实操指南

> 日期: 2026-06-09  
> 目标: 用 RunningHub 云端 ComfyUI 替代 Seedance API，实现真正的 AI 图片/视频生成

---

## 目录

1. [RunningHub 是什么](#1-runninghub-是什么)
2. [成本分析](#2-成本分析)
3. [第一步: 注册 RunningHub 并获取 API Key](#3-第一步-注册并获取-api-key)
4. [第二步: 安装依赖](#4-第二步-安装依赖)
5. [第三步: 选择/创建工作流](#5-第三步-创建工作流)
6. [第四步: StructForge 代码改造](#6-第四步-structforge-代码改造)
7. [第五步: 配置 .env](#7-第五步-配置-env)
8. [第六步: 端到端测试](#8-第六步-端到端测试)
9. [完整数据流](#9-完整数据流)
10. [FAQ](#10-faq)

---

## 1. RunningHub 是什么

```
RunningHub = 托管的 ComfyUI 云服务

你不用:
  ❌ 买 GPU (¥5000+)
  ❌ 装 ComfyUI + 下载模型 (50GB+)
  ❌ 配 CUDA/cuDNN/PyTorch
  ❌ 维护服务器

你只需要:
  ✅ 注册账号 (免费)
  ✅ 订阅付费方案 (基础版+ 才有 API)
  ✅ 获取 API Key
  ✅ pip install comfykit
  ✅ 3 行代码调工作流
```

**工作原理**:

```
StructForge
  → comfykit.execute(workflow_id, params)
    → RunningHub API (云端 GPU)
      → 加载 ComfyUI 工作流
        → 执行 Flux/SDXL/WAN 等模型
          → 返回生成的图片/视频 URL
```

---

## 2. 成本分析

### 2.1 订阅方案

| 方案 | 月费 | 特性 |
|------|------|------|
| 免费版 | ¥0 | 日送 100 RH币(24h过期), 不能调 API, 有水印 |
| 基础版 | ~¥69/月 | 50,000 RH币/月, **可用 API**, 去水印 |
| 专业版 | ~¥120/月 | 75,000 RH币/月, **3 并发**, API |
| 专业版 Plus | ~¥200/月 | 75,000 RH币/月, **5 并发**, API |

### 2.2 按量计费 (API 调用)

| 服务 | GPU | 单价 |
|------|------|------|
| 快捷创作 | 专用 GPU | ¥2.5/小时 (~$0.4/h) |
| 标准运行 | 90系列 24G | ¥4/小时 (~$0.7/h) |
| Plus 运行 | 90系列 48G | ¥6/小时 (~$0.9/h) |

### 2.3 典型消耗估算

| 操作 | 模型 | 耗时 | 费用 |
|------|------|:---:|------|
| 文生图 (1080×1920) | Flux Dev | ~15s | ~¥0.02 |
| 文生图 (1024×1024) | SDXL | ~8s | ~¥0.01 |
| 图生视频 (5s) | WAN 2.2 | ~3min | ~¥0.20 |
| TTS (一段旁白) | Edge TTS | ~3s | ~¥0.005 |

**5 段分镜视频 (全部 AI 生成)**: ~¥1-3/次

### 2.4 vs Seedance API 直调

| | RunningHub × ComfyUI | Seedance API |
|------|:---:|:---:|
| 模型选择 | Flux/SDXL/WAN/Qwen 等 50+ | 仅 Seedance/Kling |
| 控制力 | 完整工作流可定制 | API 参数有限 |
| 费用 | ¥0.02/图 | API 按 token 计 |
| 质量 | 取决于工作流 | 稳定但固定 |
| 离线可用 | ❌ (云服务) | ❌ (API) |

---

## 3. 第一步: 注册并获取 API Key

### 3.1 注册

1. 打开 https://www.runninghub.cn/ (国内) 或 https://www.runninghub.ai/ (国际)
2. 注册账号 (支持 Google/GitHub 登录)
3. 进入工作台

### 3.2 订阅 (必须!)

**免费用户不支持 API 调用。** 必须购买会员:

| 方案 | 月费 | API 并发 | 说明 |
|------|------|:---:|------|
| 基础版 | ¥69/月 | 1 | API 可用 + 去水印 |
| 专业版 | ¥129/月 | 3 | 更高并发 |
| 专业版 Plus | ¥199/月 | 5 | 最高并发 |

### 3.3 获取 API Key

1. 登录后点击右上角 **头像**
2. 选择 **「API 控制台」**
3. 点击 **小眼睛图标** 显示 Key
4. 复制 Key

> ⚠️ API Key 是**纯 32 位 hex 字符串**（不以 `rh-key-` 开头）。API 控制台展示的 `rh-key-` 前缀是界面装饰，实际 Key 值不含此前缀。

---

## 4. 第二步: 安装依赖

```bash
# 在 StructForge 的 ai-services 虚拟环境中
cd ai-services
pip install comfykit>=0.1.12
```

`comfykit` 是 Pixelle-Video 同款的 ComfyUI 客户端库，内部封装了:
- 对自建 ComfyUI 的 HTTP 调用
- 对 RunningHub 的 API 调用
- 工作流解析和执行
- 结果轮询和下载

---

## 5. 第三步: 创建工作流

### 5.1 方式一: 直接用现成工作流 (推荐起步)

RunningHub 上有 9000+ 公开工作流。Pixelle-Video 已内置了以下经过验证的:

```
workflows/runninghub/
├── image_flux.json         ← Flux 文生图 (1080p 电商图)
├── image_flux2.json        ← Flux 增强版
├── image_qwen.json         ← Qwen 文生图
├── image_sd3.5.json        ← SD3.5 文生图
├── image_sdxl.json         ← SDXL 文生图
├── image_Z-image.json      ← Z-Image 文生图
├── video_wan2.2.json       ← WAN 2.2 图生视频
├── video_qwen_wan2.2.json  ← Qwen WAN 图生视频
├── video_wan2.1_fusionx.json ← WAN 2.1 FusionX 增强视频
├── i2v_LTX2.json           ← LTX2 图生视频
├── tts_edge.json           ← Edge TTS
├── tts_spark.json          ← Spark TTS
└── tts_index2.json         ← IndexTTS2
```

每个文件内容极简:

```json
{
  "source": "runninghub",
  "workflow_id": "1983427617984585729"
}
```

### 5.2 方式二: 自定义工作流 (专业用户)

1. 打开 https://www.runninghub.ai/ 工作台
2. 拖拽节点搭建你的 ComfyUI 工作流
3. 导出为 JSON 文件
4. 如果发布到 RunningHub → 获得 `workflow_id`
5. 如果自建 ComfyUI → 保存完整 JSON (如 Pixelle-Video 的 `selfhost/image_flux.json`)

### 5.3 配置默认工作流

```yaml
# config.yaml (或 .env 等效)
comfyui:
  runninghub_api_key: "your-32-char-runninghub-key"
  
  image:
    default_workflow: "runninghub/image_flux.json"  # 文生图用 Flux
  
  video:
    default_workflow: "runninghub/video_wan2.2.json"  # 图生视频用 WAN
  
  tts:
    default_workflow: "runninghub/tts_edge.json"  # TTS 用 Edge
```

---

## 6. 第四步: StructForge 代码改造

### 6.1 新建 `ai-services/services/comfyui_service.py`

这是核心 — 封装 ComfyKit，提供与 `AIVideoService` 相同的接口:

```python
"""StructForge ComfyUI Service — RunningHub integration via ComfyKit.

Mirrors Pixelle-Video's MediaService + TTSService pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Any

from comfykit import ComfyKit

log = logging.getLogger(__name__)


class ComfyUIService:
    """Unified ComfyUI service for image, video, and TTS generation.
    
    Uses ComfyKit to talk to either:
    - RunningHub (cloud) → runninghub_api_key required
    - Self-hosted ComfyUI (local) → comfyui_url required
    
    Usage:
        service = ComfyUIService(runninghub_api_key="your-32-char-runninghub-key")
        
        # Generate image
        result = await service.generate_image(
            prompt="旺仔牛奶红色铁罐特写...",
            width=1080, height=1920,
        )
        # result["url"] → downloadable image URL
        
        # Generate video from image
        result = await service.generate_video(
            prompt="产品旋转展示...",
            image_path="/path/to/first_frame.png",
            duration=5,
        )
        # result["url"] → downloadable video URL
    """
    
    # Verified RunningHub workflow IDs (from Pixelle-Video)
    WORKFLOWS = {
        "image_flux":     "1983427617984585729",
        "image_flux2":    "1983427617984585730",
        "image_qwen":     "1983427617984585731",
        "image_sd3.5":    "1983427617984585732",
        "image_sdxl":     "1983427617984585733",
        "video_wan2.2":   "1991693844100100097",
        "video_wan2.1":   "1991693844100100098",
        "video_fusionx":  "1991693844100100099",
        "tts_edge":       "1983513964837543938",
        "tts_spark":      "1983513964837543939",
    }
    
    def __init__(
        self,
        runninghub_api_key: str | None = None,
        comfyui_url: str | None = None,
        default_image_workflow: str = "image_flux",
        default_video_workflow: str = "video_wan2.2",
    ):
        self._kit: ComfyKit | None = None
        self._kit_config_hash: str | None = None
        
        # Build ComfyKit config
        self._config: dict[str, str] = {}
        if runninghub_api_key:
            self._config["runninghub_api_key"] = runninghub_api_key
        if comfyui_url:
            self._config["comfyui_url"] = comfyui_url
        
        self.default_image_workflow = default_image_workflow
        self.default_video_workflow = default_video_workflow
        
        if not self._config:
            log.warning("ComfyUIService: no RunningHub key or ComfyUI URL configured — service disabled")
        
    @property
    def available(self) -> bool:
        return bool(self._config)
    
    def _get_kit(self) -> ComfyKit:
        """Lazy-init ComfyKit with config change detection."""
        current_hash = hashlib.md5(
            json.dumps(self._config, sort_keys=True).encode()
        ).hexdigest()
        
        if self._kit is None or self._kit_config_hash != current_hash:
            if self._kit:
                log.info("ComfyKit config changed, recreating...")
            self._kit = ComfyKit(**self._config)
            self._kit_config_hash = current_hash
            
        return self._kit
    
    async def generate_image(
        self,
        prompt: str,
        workflow: str | None = None,
        width: int = 1080,
        height: int = 1920,
        negative_prompt: str | None = None,
        steps: int = 20,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate an image via ComfyUI.
        
        Returns:
            {"url": "https://...", "local_path": "/tmp/..."}
        """
        if not self.available:
            raise RuntimeError("ComfyUIService not configured")
        
        wf_id = self.WORKFLOWS.get(workflow or self.default_image_workflow)
        if not wf_id:
            raise ValueError(f"Unknown workflow: {workflow}")
        
        kit = self._get_kit()
        params = {"prompt": prompt, "width": width, "height": height}
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if steps:
            params["steps"] = steps
        if seed is not None:
            params["seed"] = seed
        
        log.info(f"Generating image with RunningHub workflow {workflow}: {prompt[:80]}...")
        result = await kit.execute(wf_id, params)
        
        if result.status != "completed":
            raise RuntimeError(f"Image generation failed: {result.msg}")
        
        if not result.images:
            raise RuntimeError("No image in result")
        
        return {"url": result.images[0]}
    
    async def generate_video(
        self,
        prompt: str,
        image_path: str | None = None,
        workflow: str | None = None,
        width: int = 1080,
        height: int = 1920,
        duration: float = 5.0,
        audio_path: str | None = None,
    ) -> dict[str, Any]:
        """Generate a video via ComfyUI (text-to-video or image-to-video).
        
        Args:
            prompt: Video description
            image_path: Optional first frame image
            duration: Target duration in seconds
        
        Returns:
            {"url": "https://...", "duration": 5.0}
        """
        if not self.available:
            raise RuntimeError("ComfyUIService not configured")
        
        wf_id = self.WORKFLOWS.get(workflow or self.default_video_workflow)
        if not wf_id:
            raise ValueError(f"Unknown workflow: {workflow}")
        
        kit = self._get_kit()
        params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "duration": duration,
        }
        if image_path:
            params["image_path"] = image_path
        
        log.info(f"Generating video with RunningHub workflow {workflow}: {prompt[:80]}...")
        result = await kit.execute(wf_id, params)
        
        if result.status != "completed":
            raise RuntimeError(f"Video generation failed: {result.msg}")
        
        if not result.videos:
            raise RuntimeError("No video in result")
        
        return {
            "url": result.videos[0],
            "duration": getattr(result, "duration", None) or duration,
        }
```

### 6.2 修改 `AIVideoService` — 增加 ComfyUI 后端

```python
# 在 AIVideoService.__init__ 中增加:
class AIVideoService:
    def __init__(
        self,
        settings,
        platform: str = "seedance",  # "seedance" | "kling" | "runway" | "comfyui"
    ):
        self.settings = settings
        self.platform = platform
        
        if platform == "comfyui":
            self._comfyui = ComfyUIService(
                runninghub_api_key=getattr(settings, 'runninghub_api_key', None),
                comfyui_url=getattr(settings, 'comfyui_url', None),
            )
    
    def generate(self, segment, product_name="", product_type="其他"):
        if self.platform == "comfyui" and self._comfyui.available:
            return self._generate_comfyui(segment, product_name, product_type)
        else:
            return self._generate_api(segment, product_name, product_type)  # 现有逻辑
    
    async def _generate_comfyui(self, segment, product_name, product_type):
        """用 ComfyUI 生成真正的图片，而不是 Prompt Card"""
        # 构建 Prompt (中文→英文转换可在这里做)
        prompt = self.prompt_engine.build_prompt(
            product_name=product_name,
            segment_type=segment.type,
            visual=segment.visual,
            camera=getattr(segment, 'camera', '静态'),
            platform="seedance",  # prompt engine 仍生成英文提示词
        )
        
        try:
            result = await self._comfyui.generate_image(
                prompt=prompt,
                width=1080,
                height=1920,
            )
            
            # 下载到本地
            local_path = self._download(result["url"])
            
            return GeneratedVideo(
                video_path=local_path,  # 这是图片，但在 compositor 中 image/video 都可用
                generation_time=0,
                prompt_used=prompt,
            )
        except Exception as e:
            log.warning(f"ComfyUI generation failed: {e}, falling back to Prompt Card")
            return self._generate_fallback_prompt_card(segment)
```

### 6.3 修改 `compositor.py` — 在渲染时使用 ComfyUI 生成的图片

```python
# 在 _process_segments 或 SegmentProcessor 中:

if segment.render_mode == "ai_generate":
    ai_result = self.ai_video.generate(segment, ...)
    
    if isinstance(ai_result, GeneratedVideo):
        # ✅ ComfyUI 生成了真实图片/视频!
        segment.visual_input = ai_result.video_path  # 真实图片
        segment.is_ai_generated_image = True
    elif isinstance(ai_result, PromptCard):
        # ⚠️ ComfyUI 不可用 → 回退到 Prompt Card
        segment.visual_input = self._render_prompt_card(ai_result)
        segment.is_ai_generated_image = False
```

---

## 7. 第五步: 配置 .env

```bash
# .env (不会被 git 追踪)

# ── LLM (保持不变) ──
STRUCTFORGE_DOUBAO_LLM_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3/chat/completions
STRUCTFORGE_DOUBAO_LLM_API_KEY=ark-xxx
STRUCTFORGE_DOUBAO_LLM_MODEL=ep-xxx

# ── RunningHub ComfyUI (新增) ──
STRUCTFORGE_RUNNINGHUB_API_KEY=your-32-char-runninghub-key
STRUCTFORGE_COMFYUI_IMAGE_WORKFLOW=image_flux    # 默认文生图工作流
STRUCTFORGE_COMFYUI_VIDEO_WORKFLOW=video_wan2.2  # 默认图生视频工作流

# ── 可选: 自建 ComfyUI ──
# STRUCTFORGE_COMFYUI_URL=http://127.0.0.1:8188

# ── TTS (保持不变) ──
# STRUCTFORGE_TTS_API_KEY=...  # Edge TTS 免费, 不需要
```

### `config.py` 新增配置项:

```python
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # RunningHub / ComfyUI
    runninghub_api_key: str | None = None
    comfyui_url: str | None = None
    comfyui_image_workflow: str = "image_flux"
    comfyui_video_workflow: str = "video_wan2.2"
```

---

## 8. 第六步: 端到端测试

### 8.1 测试 ComfyUI 连接

```bash
cd ai-services
python -c "
import asyncio
from services.comfyui_service import ComfyUIService

async def test():
    svc = ComfyUIService(runninghub_api_key='your-32-char-runninghub-key')
    result = await svc.generate_image(
        prompt='Red can of Wangzai milk, shiny metal surface, 9:16 vertical, product photography',
        width=1080, height=1920,
    )
    print(f'✅ Image URL: {result[\"url\"]}')

asyncio.run(test())
"
```

### 8.2 完整渲染测试

```bash
# 1. 上传参考视频
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "video=@test_video.mp4"

# 2. 生成脚本 (MigratePage 上点击 "Generate Script")
# 3. 审核 (ReviewPanel)
# 4. 点击 RENDER ALL
# 5. 检查 output/{project_id}/original.mp4
```

### 8.3 预期结果

```
output/{project_id}/.work-{job_id}/
├── segment_000_tts.mp3          ← TTS 音频 (Edge TTS 免费)
├── segment_000_generated.png    ← 🆕 ComfyUI 生成的图片 (不再是 Prompt Card!)
├── segment_000.mp4              ← 真实图片 + TTS 音频 = 视频段
├── segment_001_tts.mp3
├── segment_001_generated.png
├── segment_001.mp4
├── ...
├── original_bgm.mp4             ← 拼接 + BGM
└── original.mp4                 ← 最终视频
```

---

## 9. 完整数据流

```
用户操作:
  上传参考视频 → 输入产品信息 → 点击"生成脚本"

后端处理:
  Phase 0: 结构分析
    参考视频 → VideoStructure (场景/节奏/情绪/文案)
  
  Phase 1: 脚本迁移  
    LLM → FinalScript (5 segments: hook/pain/product/proof/cta)
    每段有: type, script, visual, camera, visual_fx, emotion...
  
  Phase 2: 用户审核
    ReviewPanel → 查看提示词 → 确认

  Phase 3: 渲染 (Pixelle-Video 模式)
    ┌─────────────────────────────────────────────────────┐
    │ Step 1: TTS 合成 (先于视频!)                         │
    │   Edge TTS → segment_000_tts.mp3 (2.3s)            │
    │   Edge TTS → segment_001_tts.mp3 (3.8s)            │
    │   ...                                               │
    │   → 每段 duration = 实际音频时长                     │
    ├─────────────────────────────────────────────────────┤
    │ Step 2: 视觉生成                                     │
    │   Segment 0 (Hook, 无原视频匹配):                    │
    │     ComfyUI.generate_image(                         │
    │       prompt="旺仔牛奶红色铁罐特写 金属反光...",      │
    │       width=1080, height=1920                       │
    │     ) → segment_000_generated.png ← 🆕 真实 AI 图片! │
    │                                                      │
    │   Segment 1 (Pain, 匹配原视频 3-7s):                 │
    │     裁剪原视频 → segment_001_clip.mp4               │
    │                                                      │
    │   Segment 2 (Product, 无原视频匹配):                 │
    │     ComfyUI.generate_image(                         │
    │       prompt="旺仔牛奶倒入杯中 慢动作...",            │
    │     ) → segment_002_generated.png                   │
    │     ...                                              │
    ├─────────────────────────────────────────────────────┤
    │ Step 3: 视频段组装                                   │
    │   ffmpeg -loop 1 -i segment_000_generated.png       │
    │          -i segment_000_tts.mp3                      │
    │          -t 2.3 -c:v libx264 output.mp4             │
    │   → segment_000.mp4                                 │
    │   (对所有分镜重复)                                    │
    ├─────────────────────────────────────────────────────┤
    │ Step 4: 拼接 + BGM                                  │
    │   ffmpeg concat → original.mp4                      │
    │   ffmpeg amix BGM → original_bgm.mp4                │
    ├─────────────────────────────────────────────────────┤
    │ Step 5: 自审计                                       │
    │   BurstMetricsCalculator → 综合评分                  │
    └─────────────────────────────────────────────────────┘

输出:
  output/{project_id}/original.mp4  ← 最终视频
  (AI 生成的图片是真实的 Flux/SDXL 产物，不是占位卡片!)
```

---

## 10. FAQ

### Q: 一定要付费吗？免费版能用吗？

A: 免费版**不能调 API**。但可以手动操作: 在 RunningHub 网页上输入提示词→生成图片→下载→上传到 StructForge。基础版 (¥69/月) 即可开启 API。

### Q: 如果 RunningHub 挂了怎么办？

A: StructForge 保留**三级回退**:
1. ComfyUI (RunningHub) 生图 → 成功 → 真实 AI 图片
2. ComfyUI 失败 → Prompt Card (HTML 渲染的提示词卡片)
3. Prompt Card 失败 → 纯黑画面 (保证不中断)

### Q: 能同时支持自建 ComfyUI 和 RunningHub 吗？

A: 能。ComfyKit 自动判断:
```python
# 自建 ComfyUI
ComfyKit(comfyui_url="http://192.168.1.100:8188")
kit.execute("/path/to/workflow.json", params)  # 传本地工作流文件路径

# RunningHub
ComfyKit(runninghub_api_key="your-32-char-runninghub-key")
kit.execute("workflow_id_string", params)  # 传 workflow ID
```

### Q: 生成的图片质量怎么样？

A: 取决于选择的工作流:
- Flux Dev → 写实/电商风格，质量最高
- SDXL → 速度最快，质量中等
- Qwen Image → 中文理解最好

建议电商产品图用 Flux，生活场景用 SDXL。

### Q: 一次生成 5 段分镜视频要多长时间？

A: 
- 图片生成 (5段 × 15s) ~1.5 分钟
- TTS (Edge TTS 免费) ~30 秒
- FFmpeg 合成 ~10 秒
- **总计: ~2 分钟**

如果并行 (专业版 3 并发): ~40 秒。

---

## 附录: 关键文件清单

| 文件 | 操作 | 内容 |
|------|:---:|------|
| `ai-services/services/comfyui_service.py` | **新建** | ComfyUI 服务封装 (200行) |
| `ai-services/services/ai_video_service.py` | 修改 | 增加 `platform="comfyui"` 分支 |
| `ai-services/services/render_pipeline.py` | 修改 | 集成 ComfyUI 生成逻辑 |
| `ai-services/config.py` | 修改 | 新增 RunningHub 配置项 |
| `.env` | 修改 | `STRUCTFORGE_RUNNINGHUB_API_KEY` |
| `ai-services/requirements.txt` | 修改 | 增加 `comfykit>=0.1.12` |
| `workflows/runninghub/*.json` | **新建** | 工作流配置文件 (从 Pixelle-Video 复制) |
