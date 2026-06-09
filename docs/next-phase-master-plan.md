# StructForge 下一阶段完整优化方案

> 日期: 2026-06-10  
> 基于: Pixelle-Video 深度代码分析 + 全部已知 Bug 修复经验  
> 状态: 方案完成，待实施

---

## 优化清单总览

| # | 名称 | 来源 | 效果 | 工时 | 优先级 |
|---|------|------|------|------|--------|
| 1 | JSON Schema 注入 Prompt | Pixelle llm_service | 消除 80% LLM 校验失败 | 1h | 🔴 P0 |
| 2 | Edge TTS 免费本地模式 | Pixelle tts_service | 零 API Key 配音 | 1h | 🔴 P0 |
| 3 | LLM 结构提取评测增强 | 现有痛点 | 提高分析质量 | 1.5h | 🟡 P1 |
| 4 | 核心服务层统一管理 | Pixelle service.py | 代码整洁 + 依赖注入 | 2h | 🟡 P1 |
| 5 | 渲染后自审计闭环 | 现有功能 | 证明产品价值 | 1h | 🟡 P1 |
| 6 | 一键 AI 全填充路径 B | 用户需求 | 产品完整度 | 3h | 🟢 P2 |
| 7 | 任务历史 + 持久化 | Pixelle persistence | 用户可查历史 | 2h | 🟢 P2 |

---

## 优化 1: JSON Schema 注入 Prompt (P0, 1h)

### 问题

LLM 迁移时频繁返回格式错误的 JSON：`{id: '1', type: 'hook'}` 而非 `{version: ..., total_duration: ..., segments: [...]}`。我们用了三层防御（auto-wrap + duration修复 + ID映射）才勉强兜住，但这都是事后补救。

### 方案

在 `llm_client.py` 的 `RobustLLMClient` 中增加 `response_type` 参数。调用时传入 Pydantic 模型类，自动将 JSON Schema 注入到 prompt 末尾。

### 改动文件

**`ai-services/services/llm_client.py`** — `RobustLLMClient._call()`:

```python
def complete_json(self, prompt, *, max_tokens=2048, response_type=None):
    """Send prompt, return parsed JSON or Pydantic model."""
    raw = self._call(prompt, max_tokens=max_tokens, response_type=response_type)
    parsed = _parse_content(raw)
    if response_type is not None and isinstance(parsed, dict):
        return response_type.model_validate(parsed)
    return parsed

def _call(self, prompt, *, max_tokens=2048, response_type=None):
    # 如果有 response_type，注入 JSON Schema
    if response_type is not None:
        schema = _build_schema_instruction(response_type)
        prompt = f"{prompt}\n\n{schema}"
    # ... 其余逻辑不变
```

**`ai-services/services/llm_client.py`** — 新增函数:

```python
def _build_schema_instruction(response_type) -> str:
    """Build JSON Schema injection for the prompt."""
    import json as _json
    schema = response_type.model_json_schema()
    # 只保留关键的顶层字段，去掉嵌套细节（太长 LLM 会忽略）
    if "properties" in schema:
        keys = list(schema["properties"].keys())
        required = schema.get("required", keys)
        simplified = {
            "type": "object",
            "required": required,
            "properties": {k: schema["properties"][k] for k in keys[:15]},
        }
        schema = simplified
    schema_str = _json.dumps(schema, indent=2, ensure_ascii=False)
    return (
        "## OUTPUT FORMAT (MANDATORY)\n"
        "You MUST respond with ONLY a valid JSON object matching this schema:\n"
        f"```json\n{schema_str}\n```\n"
        "Output ONLY the JSON. No markdown, no explanation, no extra text."
    )
```

**`ai-services/services/migrator.py`** — `_generate_with_retries`:

```python
# 之前:
raw_payload = self.client.complete_json(prompt)
if isinstance(raw_payload, str):
    raw_payload = json.loads(raw_payload)
raw_payload = FinalScript._try_wrap_flat_llm_output(raw_payload)
script = FinalScript.model_validate(raw_payload)

# 之后:
script = self.client.complete_json(prompt, response_type=FinalScript)
```

### 验收

迁移时 LLM 第一次调用就返回正确的 `{version, total_duration, segments}` 格式，不再走 auto-wrap + duration修复 + ID映射。

---

## 优化 2: Edge TTS 免费本地模式 (P0, 1h)

### 问题

TTS 依赖 Volcano API Key。无 Key 时视频静音。

### 方案

在 `tts_engine.py` 中增加 `inference_mode` 参数。`"local"` 模式使用 Edge TTS（Windows 自带，`pip install edge-tts`）。

### 改动文件

**`ai-services/requirements.txt`** — 新增一行:
```
edge-tts>=6.1.0
```

**`ai-services/services/tts_engine.py`** — 增加本地模式:

```python
class TTSEngine:
    def __init__(self, ..., inference_mode: str = "api"):
        self.inference_mode = inference_mode  # "api" | "local"
    
    def synthesize(self, text, output_path, target_duration=0.0):
        if self.inference_mode == "local":
            return self._synthesize_local(text, output_path, target_duration)
        else:
            return self._synthesize_api(text, output_path, target_duration)
    
    async def _synthesize_local(self, text, output_path, target_duration):
        """Edge TTS — free, no API key needed, Windows built-in."""
        import edge_tts
        voice = VOICES.get(self.voice, "zh-CN-XiaoxiaoNeural")
        # speed → rate conversion
        rate_map = {0.8: "-20%", 0.9: "-10%", 1.0: "+0%", 1.1: "+10%",
                     1.2: "+20%", 1.3: "+30%", 1.5: "+50%"}
        rate = rate_map.get(round(self.speed, 1), "+0%")
        
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 1000
```

**`ai-services/services/compositor.py`** — TTS 调用处自动选择模式:

```python
tts = TTSEngine(
    endpoint=self.settings.tts_endpoint or None,
    api_key=self.settings.tts_api_key,
    voice=self.settings.tts_voice,
    speed=self.settings.tts_speed,
    inference_mode="local" if not self.settings.tts_api_key else "api",
)
```

### 验收

无 Volcano API Key 时，Edge TTS 自动接管。视频有配音但无需任何 API 配置。

---

## 优化 3: LLM 结构提取评测增强 (P1, 1.5h)

### 问题

当前 `extract_structure_with_retries` 在 LLM 失败后直接 `raise LLMError`。用户看到 LLMOutagePanel 但不知道是"LLM 真的挂了"还是"LLM 返回了格式错误"。

### 方案

在结构提取失败时，返回一个包含诊断信息的错误结构（而非纯异常），让前端能区分失败原因。

### 改动文件

**`ai-services/services/llm_structure.py`** — `extract_structure_with_retries`:

```python
def extract_structure_with_retries(client, prompt_context, max_attempts=3):
    """失败时不再 raise，而是返回带有 error_info 的诊断结构"""
    errors = []
    for attempt in range(1, max_attempts + 1):
        try:
            ...
            return _normalize_structure(VideoStructure.model_validate(raw_payload))
        except json.JSONDecodeError as e:
            errors.append(f"JSON解析失败: {str(e)[:100]}")
        except ValidationError as e:
            errors.append(f"Schema校验失败 ({e.error_count()} fields)")
        except LLMError as e:
            errors.append(f"LLM不可达: {str(e)[:100]}")
    
    # 返回诊断信息而非直接崩溃
    return _build_diagnostic_structure(prompt_context, errors)
```

### 验收

前端结构分析失败时，展示具体原因（"LLM 返回了非 JSON 文本" vs "LLM 服务超时"），用户可针对性修复。

---

## 优化 4: 核心服务层统一管理 (P1, 2h)

### 问题

每次 `compositor.render()` 都 new 一个 `TTSEngine`。`MigratorService` 创建自己的 `DoubaoSeedClient`。没有统一的依赖管理。

### 方案

新建 `StructForgeCore` 类，集中管理所有服务，支持懒加载和单例。

### 新增文件

**`ai-services/services/core.py`**:

```python
class StructForgeCore:
    """统一服务层 — 所有能力通过一个对象访问"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm = None
        self._tts = None
        self._ai_video = None
    
    @property
    def llm(self) -> RobustLLMClient:
        if self._llm is None:
            self._llm = RobustLLMClient(
                str(self.settings.doubao_llm_endpoint or ""),
                str(self.settings.doubao_llm_api_key or ""),
                str(self.settings.doubao_llm_model),
            )
        return self._llm
    
    @property
    def tts(self) -> TTSEngine:
        if self._tts is None:
            self._tts = TTSEngine(
                endpoint=self.settings.tts_endpoint or None,
                api_key=self.settings.tts_api_key,
                voice=self.settings.tts_voice,
                speed=self.settings.tts_speed,
                inference_mode="local" if not self.settings.tts_api_key else "api",
            )
        return self._tts
    
    @property
    def ai_video(self) -> AIVideoService:
        if self._ai_video is None:
            self._ai_video = AIVideoService(self.settings)
        return self._ai_video
```

### 改动文件

- `compositor.py`: `self.core = core` 代替 `self.settings`，`core.tts` 代替 `TTSEngine(...)`
- `migrator.py`: 构造函数接受 `core` 而非 `settings`，`core.llm` 代替 `DoubaoSeedClient(settings)`
- `routes/*.py`: 创建 `core` 实例并传给所有 service

### 验收

所有服务通过 `core.llm` / `core.tts` 访问，不再重复创建连接。

---

## 优化 5: 渲染后自审计闭环 (P1, 1h)

### 问题

当前审计功能独立——用户上传视频 → 分析 → 审计。但没有"渲染完成后自动审计自己的作品"的功能。

### 方案

在 `VideoRenderPipeline._finalize()` 中，渲染完成后自动运行审计。

### 改动文件

**`ai-services/services/render_pipeline.py`** — `_finalize()`:

```python
async def _finalize(self, ctx):
    # ... 现有逻辑 ...
    
    # ── Self-audit: analyze the generated video ──
    if ctx.output_path and ctx.output_path.exists():
        try:
            audit = self._run_self_audit(ctx)
            ctx.script.metadata["self_audit"] = audit
            ctx.warnings.append(f"Self-audit: overall={audit.get('overall_score', '?')}")
        except Exception:
            pass
```

### 验收

渲染完成后，在 `metadata.self_audit` 中可看到自审计分数。前端展示"我们的产品，连自己都在用它来定义和创造爆款"。

---

## 优化 6: 一键 AI 全填充路径 B (P2, 3h)

### 问题

StructForge 只有"路径 A"：分析爆款 → 提取结构 → 用户上传素材 → 渲染。没有"路径 B"：分析爆款 → 提取结构 → AI 自动生成所有画面 → 直接出片。

### 方案

在 MigratePage 增加"一键 AI 全填充"按钮。不需要用户上传素材。

### 新增/改动文件

1. **`src/pages/MigratePage.tsx`**: 增加"一键 AI 全填充"按钮
2. **`ai-services/routes/migrate.py`**: 新增 `POST /{id}/auto-fill` 端点
3. **`ai-services/services/migrator.py`**: 新增 `auto_fill()` 方法——为所有缺素材分镜调用 `AIVideoService`

### 验收

用户上传样例视频 → 分析 → 输入新产品 → 点"一键 AI 全填充" → 等待 1-2 分钟 → 完整视频（所有分镜都有 AI 生成画面或提示词卡片）。

---

## 优化 7: 任务历史 + 持久化 (P2, 2h)

### 问题

用户无法查看之前生成过的视频。每次都要重新上传、分析、生成。

### 方案

新建 `HistoryService`，在 SQLite 中增加 `history` 表，记录每次渲染结果。

### 新增/改动文件

1. **`ai-services/services/history_service.py`**: 历史管理服务
2. **`ai-services/models/repository.py`**: 增加 `history` 表
3. **`src/pages/ProjectListPage.tsx`**: 展示历史记录

### 验收

项目列表页可以查看"历史生成记录"，点击可直接播放之前的视频，不需要重新生成。

---

## 实施顺序

```
第 1 批（2h）:
  优化 1: JSON Schema 注入 Prompt   ← 消除 LLM 校验失败
  优化 2: Edge TTS 免费本地模式     ← 零 API Key 配音

第 2 批（4.5h）:
  优化 3: LLM 结构提取评测增强       ← 诊断信息
  优化 4: 核心服务层                ← 代码整洁
  优化 5: 自审计闭环                ← 证明价值

第 3 批（5h）:
  优化 6: 一键 AI 全填充路径 B      ← 产品完整度
  优化 7: 任务历史                  ← 用户体验
```
