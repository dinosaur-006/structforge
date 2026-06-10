# Pixelle-Video 深度代码分析 — StructForge 可借鉴的逻辑思维

> 日期: 2026-06-09  
> 对比维度: 6 个核心服务模块  
> 状态: 分析完成

---

## 模块 1: LLM 调用 — 结构化输出模式

### Pixelle 的做法 (`llm_service.py`)

```python
# 核心：LLM 调用原生支持 Pydantic 结构化输出
async def __call__(self, prompt, response_type=None, **kwargs):
    if response_type:
        return await self._call_with_structured_output(
            prompt=prompt, response_type=response_type
        )

# 关键：把 Pydantic model 的 JSON Schema 追加到 prompt 末尾
def _get_json_schema_instruction(self, response_type):
    schema = response_type.model_json_schema()
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    return f"""## IMPORTANT: JSON Output Format Required
You MUST respond with ONLY a valid JSON object.
{json.dumps(schema, ...)}

Output ONLY the JSON object, nothing else."""

# 解析时三级 fallback:
# 1. 直接 json.loads
# 2. 从 markdown ```json ``` 代码块中提取
# 3. 从 { 到 } 提取任意 JSON 对象
# 都不行 → ValueError(详细的错误信息)
```

### StructForge 的当前做法

```python
# DoubaoSeedClient 调用 → 返回原始文本
# 每次调用方自己 json.loads + 异常处理
# LLM 返回格式错误 → 18 validation errors → 脚本生成失败

# 我们的修复: _try_wrap_flat_llm_output + 三层防御
# 这些都是"事后补救"，不是"事前预防"
```

### 可借鉴的逻辑

1. **JSON Schema 注入到 Prompt**: 在每次 LLM 调用时，把目标 Pydantic 模型的 JSON Schema 追加到 prompt 末尾。LLM 看到了"你要输出这个格式"，产出质量大幅提升。这能减少 80% 的 Pydantic 校验失败。

2. **三级 JSON 解析**: 直接解析 → markdown 代码块 → 任意 {} 提取。当前 `llm_client.py` 已有类似逻辑，但没有 prompt 注入这一步。

3. **Structured Output 作为一等公民**: `response_type` 参数原生支持。调用方不需要手动 `json.loads` + `model_validate`。

```python
# 改造后的调用（对比当前）:
# 当前: 
raw = client.complete_json(prompt)
if isinstance(raw, str): raw = json.loads(raw)
script = FinalScript.model_validate(raw)

# 改后:
script = client.complete(prompt, response_type=FinalScript)
```

---

## 模块 2: 核心服务层 — 统一初始化与管理

### Pixelle 的做法 (`service.py`)

```python
class PixelleVideoCore:
    """统一服务层 — 所有能力通过一个对象访问"""
    
    def __init__(self, config_path):
        self.config = config_manager  # 支持热重载
        self.llm = LLMService(self.config)
        self.tts = TTSService(self.config, core=self)
        self.media = MediaService(self.config, core=self)
        self.video = VideoService()
        self.frame_processor = FrameProcessor(self)
        self.persistence = PersistenceService()
        self.history = HistoryManager()

# 使用:
pixelle_video = PixelleVideoCore("config.yaml")
answer = await pixelle_video.llm("Explain atomic habits")
audio = await pixelle_video.tts("Hello world")
```

### StructForge 的当前做法

```python
# 每个服务独立创建，到处散落
class Compositor:
    def render(self, ...):
        tts = TTSEngine(endpoint=..., api_key=..., voice=...)
        bgm = BGMEngine(bgm_dir=..., ffmpeg_path=...)
        ai_video = AIVideoService(Settings())
        # TTS 引擎被创建了 N 次，每次 render 都新建

class MigratorService:
    def __init__(self, ...):
        self.client = DoubaoSeedClient(self.settings)
        self.evaluator = ResultEvaluator(endpoint=..., api_key=...)
```

### 可借鉴的逻辑

1. **单例核心对象**: 所有服务统一管理，避免重复创建（TTS 每次 render 都 new 一次，浪费连接资源）
2. **配置热重载**: `config_manager` 读取 yaml → settings 对象变化自动生效，不需要重启服务端
3. **依赖注入**: `TTSService(config, core=self)` — 核心对象传给子服务，子服务可以访问其他服务

---

## 模块 3: TTS 引擎 — 双模式 + 本地免费方案

### Pixelle 的做法 (`tts_service.py`)

```python
class TTSService:
    async def __call__(self, text, inference_mode, voice, speed, **params):
        if mode == "local":
            return await self._call_local_tts(text, voice, speed, output)
        else:  # comfyui
            return await self._call_comfyui_workflow(...)

# 本地模式: Edge TTS（完全免费、无需 API Key）
# ComfyUI 模式: 声音克隆、自定义音色、多语言

# speed → rate 转换表 (tts_voices.py)
speed_to_rate = {0.5: "-50%", 0.8: "-20%", 1.0: "+0%", 1.2: "+20%", ...}
```

### StructForge 的当前做法 (`tts_engine.py`)

```python
# 只有 Volcano TTS API 一种方式
# 需要 API Key → 无法免费使用
# speed → speech_rate 转换：int((speed - 1.0) * 50)
```

### 可借鉴的逻辑

1. **Edge TTS 作为免费 fallback**: 添加 `inference_mode="local"` 参数，当 API Key 未配置时使用 Edge TTS。Windows 自带 Edge TTS 引擎，零依赖、零成本。

2. **双模式路由**: `if local → Edge TTS; else → Volcano API`。与我们的 `AIVideoService` 设计模式一致。

```python
# 实现很简单（不需要额外依赖）:
import edge_tts  # pip install edge-tts (纯 Python, 无系统依赖)
async def edge_tts(text, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)
```

---

## 模块 4: 配置热重载 — 不改代码调参数

### Pixelle 的做法 (`config/manager.py`)

```python
class ConfigManager:
    """配置管理器 — 支持热重载"""
    
    def __init__(self, config_path):
        self._config_path = config_path
        self.config = self._load()  # Pydantic model
    
    def reload(self):
        """重新加载配置（不需要重启）"""
        self.config = self._load()
    
    @property
    def config(self):
        return self._config  # 每次访问都是最新配置
```

### StructForge 的当前做法

```python
# Settings 在启动时读取 .env，之后不变
# 修改 config 需要重启服务端
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ...)
```

### 可借鉴的逻辑

1. **yaml 配置代替 .env**: yaml 可嵌套、可注释、可热重载。`.env` 只能单层 key=value。
2. **配置热重载接口**: `POST /api/v1/config/reload` — 前端可以触发配置重载。
3. **Settings 支持 reload()**: 在 `config.py` 中增加一个 `reload()` 方法。

---

## 模块 5: 内容生成工具 — LLM 调用的工程化

### Pixelle 的做法 (`content_generators.py`)

```python
# 每个 LLM 调用任务是一个独立函数，返回结构化数据

async def generate_narrations_from_topic(llm, topic, n_scenes, min_words, max_words):
    """根据主题生成分镜叙述 → List[str]"""
    prompt = NARRATION_PROMPT.format(topic=topic, n=n_scenes, ...)
    return await _call_with_retry(llm, prompt, parser=_parse_narrations)

async def generate_image_prompts(llm, narrations, ...):
    """根据叙述生成图像提示词 → List[str]"""
    ...

async def generate_title(llm, text, strategy):
    """根据文本生成标题 → str"""
    ...

# 每个函数都有独立的 retry + fallback
async def _call_with_retry(llm, prompt, parser, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await llm(prompt, response_type=SomeModel)
            return parser(result)
        except Exception:
            if attempt == max_retries - 1: raise
```

### StructForge 的当前做法

```python
# LLM 调用散落在各个 service 中
# migrator.py, llm_structure.py, burst_auditor.py, ...
# 每个地方都有自己独立的 retry + error handling
```

### 可借鉴的逻辑

1. **LLM 任务函数化**: 每个 LLM 调用包装为独立函数，统一 retry + fallback + 日志。
2. **parser 参数**: LLM 返回 → parser 解析 → 返回纯数据结构。调用方不关心 JSON 解析。
3. **Prompt 模板集中管理**: 所有 prompt 在 `prompts/` 目录下统一维护，而不是散落在各个 service 的字符串中。

---

## 模块 6: 持久化与历史 — 状态追踪

### Pixelle 的做法 (`persistence.py` + `history_manager.py`)

```python
# 每个任务有完整的状态追踪
class PersistenceService:
    async def save_task_metadata(task_id, metadata):
        """保存任务元数据到文件系统"""
    async def save_storyboard(task_id, storyboard):
        """保存分镜数据"""
    async def load_task(task_id) -> dict:
        """加载历史任务"""

class HistoryManager:
    async def list_tasks(limit=20) -> list[dict]:
        """列出最近任务"""
    async def delete_task(task_id):
        """删除任务"""
```

### StructForge 的当前做法

```python
# 用 SQLite 做持久化（repository.py）
# 但没有任务历史管理
# 用户无法查看/恢复之前的渲染结果
```

### 可借鉴的逻辑

1. **文件系统 + SQLite 双存储**: SQLite 存结构化数据，文件系统存大文件（视频、图片）。当前我们的 `data/outputs/{project_id}/` 就是这个模式，但没有历史索引。
2. **任务历史 API**: `GET /api/v1/history` — 用户可以查看历史生成的视频，不需要每次都重新分析。

---

## 优先级排序

| 优先级 | 借鉴内容 | 文件 | 效果 | 工时 |
|--------|---------|------|------|------|
| 🔴 P0 | JSON Schema 注入 Prompt | `llm_client.py` | 减少 80% Pydantic 校验失败 | 1h |
| 🔴 P0 | Edge TTS 免费本地模式 | `tts_engine.py` | 零 API Key 也能配音 | 1h |
| 🟡 P1 | 核心服务层统一管理 | `service.py` (新建) | 避免重复创建，依赖注入 | 2h |
| 🟡 P1 | LLM 任务函数化 + Prompt 集中管理 | `prompts/` 目录 | 代码整洁，prompt 可维护 | 3h |
| 🟢 P2 | 配置热重载 + yaml | `config.py` | 不改代码调参数 | 2h |
| 🟢 P2 | 任务历史 + 持久化 | `persistence.py` | 用户可查看历史 | 3h |
