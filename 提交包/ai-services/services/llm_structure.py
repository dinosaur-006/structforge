from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from config import Settings
from models.schemas import VideoStructure


class StructureExtractionError(RuntimeError):
    pass


class JsonCompletionClient(Protocol):
    def complete_json(self, prompt: str) -> object:
        ...


class DoubaoSeedClient:
    """Doubao Seed LLM client — delegates to shared RobustLLMClient.

    Backward-compatible wrapper. The actual retry/timeout logic lives in
    services.llm_client.RobustLLMClient.

    Pass ``_client`` to inject a pre-configured RobustLLMClient (e.g. with
    a custom timeout for large prompts like migration).
    """

    def __init__(self, settings: Any, *, _client: Any = None) -> None:
        if _client is not None:
            self._client = _client
        else:
            from services.llm_client import RobustLLMClient
            endpoint = str(settings.doubao_llm_endpoint or "")
            api_key = str(settings.doubao_llm_api_key or "")
            model = str(settings.doubao_llm_model)
            self._client = RobustLLMClient(endpoint, api_key, model)

    def complete_json(self, prompt: str) -> object:
        try:
            return self._client.complete_json(prompt, max_tokens=2048)
        except Exception as exc:
            raise StructureExtractionError(str(exc)) from exc


class LocalStructureClient:
    """Fallback client that builds a structure from local heuristics."""

    def __init__(self, prompt_context: dict[str, Any]) -> None:
        self.prompt_context = prompt_context

    def complete_json(self, prompt: str) -> object:
        return build_local_structure_payload(self.prompt_context)


PROMPT_TEMPLATE = """
你是 StructForge 的首席视频结构分析师。你对短视频的拆解直接决定了后续成片的质量。
你的任务是将输入的非结构化多模态数据（ASR、关键帧标签、元数据）收敛为极其严谨的 VideoStructure JSON。

## 严格打分与分类约束
1. 严禁给出平庸的、连续的 70-80 分。带货短视频是精密说服机器，好就是好，差就是差。
2. 每一个分镜必须根据其真实的视觉画面和文本特征，提取出绝对客观的 visual_keywords。

## 统一视觉特征词库（白名单）— 你只能在此选择，严禁自创
- 人物动作类: [达人出镜, 面部特写, 皱眉抓狂, 震惊捂嘴, 举起商品, 撕开包装, 指向屏幕, 微笑展示, 侧脸展示, 大口咀嚼, 倒出液体, 搅拌动作, 擦拭清洁, 涂抹演示]
- 商品形态类 — 美妆洗护: [瓶身特写, 液体流动, 膏体拉丝, 泡沫细腻, 材质反光, 内部拆解, 颜色对比, 质地展示, 包装特写, 挤压出液]
- 商品形态类 — 食品饮料: [食材特写, 酱汁流淌, 冒泡沸腾, 油炸翻滚, 调味撒粉, 拉丝芝士, 切面展示, 麻辣红油, 叠放展示, 手撕特写, 蒸腾热气, 冰霜质感, 颗粒质感, 金黄酥脆, Q弹质感]
- 商品形态类 — 电子3C: [屏幕亮光, 金属拉丝, 接口特写, 纤薄侧面, 运行光效, 内部结构, 握持手感, 充电指示灯]
- 商品形态类 — 服饰纺织: [面料特写, 针脚走线, 试穿展示, 挂拍陈列, 弹性拉伸, 防水测试]
- 场景与背景: [居家浴室, 卧室梳妆台, 现代办公室, 纯色背景, 嘈杂街头, 实验室场景, 厨房场景, 户外自然光, 餐桌场景, 便利店货架, 零食堆头, 冰箱冷藏层, 夜市灯光, 咖啡厅角落]
- 情绪与氛围: [高能炸裂, 悬念反转, 温馨治愈, 专业严谨, 紧迫焦虑, 惊喜意外, 食欲大开, 解压舒适]
- 特效与转场: [震屏冲击, 快速闪切, 慢动作特写, 放大聚焦, 淡入溶解, 缩放弹跳]
- 食品特有: [金黄酥脆, 蒸腾热气, 麻辣红油, 酱汁四溢, 爽滑拉丝, 冰爽水珠, 颗粒饱满, 软糯拉丝]

## 产品信息提取 — 极其严格的反幻觉规则
这是整个分析最关键的步骤，产品名错了全盘皆错。

### 首先检查 ASR 状态：
- 输入上下文中有一个 `asr_is_empty` 字段。
- **如果 asr_is_empty 为 true**：此视频没有语音！你必须在 productName 中填写 "未识别（无语音）"，在 coverLabel 中使用视觉标签中最高频的2-3个词组合。严禁猜测产品品类！
- **如果 asr_available 为 false**：ASR 质量差或失败，降低置信度，productName 从视觉+文件名推断但不编造品牌。

### 产品名提取优先级（ASR可用时）：
1. **ASR口播中明确说出的产品名** → 最高优先级
2. **OCR 画面中的产品名文字** → 第二优先级
3. **视觉标签推断** → 最低优先级

### 绝对禁止：
- ❌ 禁止根据外观猜品类。白色膏体=面霜/牙膏/面包酱/奶油
- ❌ 禁止编造品牌名
- ❌ 禁止把质地描述当产品名（"泡沫""慕斯"→不是产品名）
- ❌ 禁止在 ASR 为空时猜测具体产品名

## 五维评分体系（0-100，严格打分，不使用模糊范围）
### 1. hook_strength（开头吸引力）— 权重最高
90-100（爆款级）: 第1帧认知冲击，视听文三者协同创造不可抗拒的停留理由。"等等...这不可能"、"我测了47款，只有一款有效"。
70-89（专业级）: 开头明确有效，画面有吸引力，文案提出问题或痛点。大多数 MCN 出品封顶于此。
50-69（合格但平庸）: 有Hook但可预测。"这个产品太强了"——用户今天已看过100遍。
30-49（较弱）: 开头偏慢，文字先行，品牌Logo出镜。等有意思的内容出现时用户已划走。
0-29（缺失）: 根本无Hook，以慢镜头、标题卡或"欢迎来到我的频道"开头。

### 2. product_exposure_timing（产品露出时机）
90-100: 产品作为问题的自然解决方案在3-5秒内出场，产品露出不象广告而象救星。
70-89: 产品在5-8秒内展示，方式专业但不够惊艳。
50-69: 产品出现过晚(>8秒)或过早缺乏铺垫，镜头平庸。
30-49: 产品几乎看不到或埋在广角镜头里，无英雄时刻。
0-29: 用户不知道在卖什么。

### 3. selling_point_proof（卖点证明力）
90-100: 无可辩驳的证据——具体数据、真实对比效果、实测镜头。在产品怀疑者提问前已回答问题。
70-89: 好的视觉支撑来证明卖点，有使用场景展示和具体性。
50-69: 泛泛好处描述，视觉支撑弱。"质量很好"配微笑镜头，无区分度。
30-49: 纯断言。"行业领先""品质卓越""你一定会喜欢"——无证据无演示无数据。
0-29: 完全无卖点或明显虚假。

### 4. pacing_compactness（信息密度与节奏）
90-100: 剪辑大师级。切换点与语音节奏精准对齐。信息密度高但从不让压迫。
70-89: 节奏稳定，少数冗余，整体流畅。
50-69: 有明显拖沓，某些分镜时长不合理。
30-49: 严重冗余或窒息式快节奏。
0-29: 无节奏意识，信息密度极低。

### 5. cta_persuasiveness（转化号召力）
90-100: 具体指令+稀缺性+零风险承诺+情感共鸣四合一。
70-89: 明确的CTA存在，有一定说服力。
50-69: CTA存在但弱，"快来买吧"级别。
30-49: 模糊CTA，用户看完不知道下一步该做什么。
0-29: 完全无CTA。

## 平台对标基准（评分必须参考）
- 综合分: 95%视频<65, 75+已是专业水平, 85+有Top100潜力
- 完播率<30%→0-30分, 30-50%→50-70分, >50%→80-100分
- 点击率<3%→0-30分, 3-6%→50-70分, >6%→80-100分

## 输出格式
返回严格符合 VideoStructure schema 的 JSON 对象。所有文字字段必须是中文。
{{
  "meta": {{"duration": number, "resolution": string, "shots": number, "coverLabel": string, "productName": string}},
  "script": [
    {{"id": string, "type": "hook|pain|product|proof|cta", "label": string,
      "start": number, "end": number, "duration": number, "goal": string,
      "copy": "干净的口播文案", "visual": "画面描述",
      "visual_keywords": ["达人出镜", "震惊捂嘴"],
      "healthScore": number}}
  ],
  "rhythm": [{{"second": number, "cuts": number, "emotion": number, "highlight": boolean}}],
  "packaging": {{"subtitleStyle": string, "transitions": [string], "overlays": [string]}},
  "health": {{"hook_strength": number, "product_exposure_timing": number, "selling_point_proof": number, "pacing_compactness": number, "cta_persuasiveness": number, "overall": number}}
}}

## 关键规则
1. 分镜级 healthScore 必须反映该分镜完成其角色的程度。Hook 85+ 意味着"这个开头确实能让人停下来"。
2. rhythm 中 emotion >= 0.9 是"起鸡皮疙瘩/笑出声/倒吸一口气"。0.5是"还行有点意思"。不要给平淡内容打0.7+。
3. visual_keywords 每一段必须至少填2个，且只能从白名单中选。
4. productName 必须从视频中提取真实的品牌+产品名，不是文件名。
5. 综合分 overall = 5维加权平均（hook权重最高），严禁全部打一样的分。

输入上下文（多模态融合数据）：
{context_json}
"""


def build_prompt(prompt_context: dict[str, Any], attempt: int) -> str:
    context = dict(prompt_context)
    context["attempt"] = attempt
    return PROMPT_TEMPLATE.format(context_json=json.dumps(context, ensure_ascii=False, indent=2))


def extract_structure_with_retries(
    *,
    client: JsonCompletionClient,
    prompt_context: dict[str, Any],
    max_attempts: int = 3,
) -> VideoStructure:
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        prompt = build_prompt(prompt_context, attempt)
        try:
            raw_payload = client.complete_json(prompt)
            if isinstance(raw_payload, str):
                raw_payload = json.loads(raw_payload)
            return _normalize_structure(VideoStructure.model_validate(raw_payload))
        except (json.JSONDecodeError, ValidationError, StructureExtractionError) as exc:
            errors.append(str(exc))

    # All LLM attempts failed — raise hard error. Structure extraction is NOT degradable.
    from services.llm_client import LLMError
    raise LLMError(
        f"视频结构分析失败，LLM 调用 {max_attempts} 次全部失败",
        suggestion="请检查 API Key 和网络连接。如需离线工作，可在前端选择「离线模式」使用规则引擎。",
        retryable=True,
    )


def build_local_structure_payload(prompt_context: dict[str, Any]) -> dict[str, Any]:
    meta = prompt_context.get("meta", {})
    duration = float(meta.get("duration") or 35.0)
    resolution = str(meta.get("resolution") or "unknown")
    scenes = prompt_context.get("scenes") or []
    shots = len(scenes) if scenes else int(meta.get("shots") or 5)
    boundaries = _segment_boundaries(duration)

    # Dynamic segment detection — not forced 5-segment template.
    # Use scene boundaries to estimate natural segment count.
    natural_segments = max(3, min(len(scenes) + 1, 8))
    segment_types = ["hook"] + ["pain"] * max(0, natural_segments - 4) + ["product", "proof", "cta"]
    # Truncate or pad to match natural_segments
    if len(segment_types) > natural_segments:
        segment_types = segment_types[:natural_segments]
    elif len(segment_types) < natural_segments:
        # Insert extra segments between proof and cta
        insert_at = len(segment_types) - 1
        for _ in range(natural_segments - len(segment_types)):
            segment_types.insert(insert_at, "proof")

    segment_labels = {"hook": "Hook", "pain": "痛点", "product": "产品引入", "proof": "卖点证明", "cta": "CTA"}
    goals = {"hook": "stop_scroll", "pain": "problem_framing", "product": "solution_intro", "proof": "selling_point_proof", "cta": "conversion"}
    base_scores = {"hook": 55, "pain": 50, "product": 52, "proof": 48, "cta": 45}

    step = duration / max(natural_segments, 1)
    script = []
    for i, stype in enumerate(segment_types):
        seg_id = f"seg-{stype}-{i + 1}" if segment_types.count(stype) > 1 else f"seg-{stype}"
        script.append(_segment(
            seg_id, stype, segment_labels[stype],
            round(i * step, 2), round(min((i + 1) * step, duration), 2),
            goals[stype], base_scores.get(stype, 50),
        ))
    rhythm = _rhythm_points(duration, scenes)
    health = {
        "hook_strength": 55,
        "product_exposure_timing": 52,
        "selling_point_proof": 48,
        "pacing_compactness": 50,
        "cta_persuasiveness": 45,
        "overall": 50,
    }
    # Preserve product name from original analysis when available.
    product_name = "未知商品"
    if prompt_context:
        orig_meta = prompt_context.get("meta") or {}
        product_name = str(orig_meta.get("productName") or prompt_context.get("product_info") or "")
        if not product_name or product_name in ("", "未知商品"):
            # Try project info
            proj = prompt_context.get("project") or {}
            brief = proj.get("product_info") or {}
            if isinstance(brief, dict):
                product_name = str(brief.get("productName") or "")
            elif isinstance(brief, str):
                product_name = brief
            if not product_name or product_name in ("", "未知商品"):
                product_name = "未知商品"

    return {
        "meta": {
            "duration": duration,
            "resolution": resolution,
            "shots": shots,
            "coverLabel": "Generated keyframe cover",
            "productName": product_name,
        },
        "script": script,
        "rhythm": rhythm,
        "packaging": {
            "subtitleStyle": ["Large clean sans-serif", "High contrast caption band"],
            "transitions": ["Hard cut", "Push transition"],
            "overlays": ["Product label", "Offer annotation"],
        },
        "health": health,
    }


def _segment(
    segment_id: str,
    segment_type: str,
    label: str,
    start: float,
    end: float,
    goal: str,
    score: int,
) -> dict[str, Any]:
    return {
        "id": segment_id,
        "type": segment_type,
        "label": label,
        "start": round(start, 2),
        "end": round(end, 2),
        "duration": round(max(end - start, 0.0), 2),
        "goal": goal,
        "copy": f"{label} message extracted from sample structure",
        "visual": f"{label} visual moment based on keyframes",
        "healthScore": score,
    }


def _segment_boundaries(duration: float) -> list[float]:
    return [
        0.0,
        min(duration, max(3.0, duration * 0.10)),
        min(duration, max(8.0, duration * 0.25)),
        min(duration, max(12.0, duration * 0.40)),
        min(duration, max(24.0, duration * 0.72)),
        duration,
    ]


def _rhythm_points(duration: float, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    point_count = max(5, min(8, int(duration // 5) + 1))
    step = duration / max(point_count - 1, 1)
    highlight_index = max(1, point_count // 2)
    points: list[dict[str, Any]] = []
    for index in range(point_count):
        second = round(index * step, 2)
        cuts = _cuts_near_second(second, scenes)
        emotion = min(1.0, 0.45 + index * 0.08)
        point = {"second": second, "cuts": max(cuts, 1 + (index % 3)), "emotion": round(emotion, 2)}
        if index == highlight_index:
            point["highlight"] = True
        points.append(point)
    return points


def _cuts_near_second(second: float, scenes: list[dict[str, Any]]) -> int:
    lower = max(0, (second - 5) * 1000)
    upper = (second + 5) * 1000
    return sum(1 for scene in scenes if lower <= scene.get("start_ms", 0) <= upper)


def _extract_content(payload: dict[str, Any]) -> object:
    if "choices" in payload:
        message = payload["choices"][0].get("message", {})
        return message.get("content", {})
    if "content" in payload:
        return payload["content"]
    return payload


def _normalize_structure(structure: VideoStructure) -> VideoStructure:
    payload = structure.model_dump(mode="json", by_alias=True)

    # ── Patch missing productName ──
    meta = payload.get("meta") or {}
    if not meta.get("productName"):
        meta["productName"] = "未知商品"
        payload["meta"] = meta

    # ── Patch missing visual_keywords ──
    for seg in payload.get("script") or []:
        if "visual_keywords" not in seg or not seg.get("visual_keywords"):
            seg["visual_keywords"] = ["纯色背景"]

    # ── Patch rhythm if too short ──
    rhythm = payload.get("rhythm") or []
    if len(rhythm) < 5:
        existing = rhythm
        by_second = {float(point["second"]): point for point in existing}
        duration = float(meta.get("duration") or 0)
        if duration <= 0:
            duration = max((float(point["second"]) for point in existing), default=4.0)
        step = duration / 4 if duration else 1.0
        for index in range(5):
            second = round(index * step, 2)
            by_second.setdefault(
                second,
                {
                    "second": second,
                    "cuts": 1 + (index % 3),
                    "emotion": round(min(1.0, 0.45 + index * 0.1), 2),
                    "highlight": index == 2,
                },
            )
        payload["rhythm"] = [by_second[key] for key in sorted(by_second)][: max(5, len(by_second))]

    return VideoStructure.model_validate(payload)


def _parse_json_content(content: str) -> object:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        candidate = _first_json_object(content)
        if candidate is None:
            raise
        return json.loads(candidate)


def _first_json_object(content: str) -> str | None:
    start = content.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(content)):
            char = content[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start : index + 1]
        start = content.find("{", start + 1)
    return None
