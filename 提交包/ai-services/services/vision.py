from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from config import Settings


VISION_PROMPT = """
你是绝对理性的视觉分析机器，负责逐帧抓取画面中的物理客观事实。你的分析结果将直接用于产品识别，
因此你必须尽可能从画面中提取可辨识的产品信息。

## OCR — 最重要的任务
逐帧仔细读取画面中出现的**所有可见文字**，包括：
- 产品包装上的品牌名、产品名、成分表
- 字幕文字、价格标签、促销文案
- 任何出现在画面中的印刷或手写文字
将识别到的文字原样填入 ocr 数组。不要猜测，只填写能看清的文字。

## product_type — 产品类别推断
根据画面中的产品外观、包装、使用场景，从以下类目中选择最匹配的一个填入 product_type：
[食品饮料, 美妆护肤, 数码电子, 服装配饰, 家居日用, 母婴用品, 运动户外, 图书文具, 医药健康, 其他]

## 核心映射字典 — 严格约束
1. shot_type: [微距特写, 局部中景, 人物全景, 极度俯拍, 平视特写] 之一
2. motion_type: [静态无动, 缓慢推近, 水平横移, 快速冲镜, 手持微晃] 之一
3. emotion_label: [高能炸裂, 悬念反转, 温馨治愈, 专业严谨, 紧迫焦虑, 惊喜意外] 之一
4. tags: 从以下词库选取，优先选择能辨识产品特征的标签：
   人物类: 达人出镜, 面部特写, 皱眉抓狂, 震惊捂嘴, 举起商品, 涂抹演示, 撕开包装, 指向屏幕, 微笑展示
   产品类: 瓶身特写, 液体流动, 膏体拉丝, 泡沫细腻, 材质反光, 内部拆解, 颜色对比, 质地展示, 包装特写
   食品特化: 食物特写, 颗粒状产品, 彩色糖果, 独立小包装, 拉丝效果, 酥脆质感, 咀嚼展示
   场景类: 居家浴室, 卧室梳妆台, 现代办公室, 纯色背景, 嘈杂街头, 实验室场景, 厨房场景, 户外自然光
   特效类: 震屏冲击, 快速闪切, 慢动作特写, 放大聚焦

返回 JSON:
{"frames":[{"index":1,"description":"画面物理描述","shot_type":"微距特写","motion_type":"缓慢推近","emotion_label":"温馨治愈","ocr":["识别到的文字"],"product_type":"食品饮料","tags":["包装特写","彩色糖果"],"dominant_colors":["#FF6B35","#FFFFFF"]}]}
""".strip()


def analyze_frames(frame_paths: list[Path], settings: Settings) -> dict[str, Any]:
    configuration = _visual_configuration(settings)
    if configuration is None:
        return {
            "vision_status": "skipped",
            "frames": [_placeholder_frame(index, path) for index, path in enumerate(frame_paths, start=1)],
        }

    endpoint, api_key = configuration
    frames: list[dict[str, Any]] = []
    for batch_start in range(0, len(frame_paths), 5):
        batch = frame_paths[batch_start : batch_start + 5]
        batch_result = _send_vision_batch(batch, batch_start, endpoint, api_key, settings)
        if batch_result["status"] != "completed":
            return {
                "vision_status": "failed",
                "vision_error": batch_result["error"],
                "frames": frames + batch_result["frames"],
            }
        frames.extend(batch_result["frames"])
    return {"vision_status": "completed", "frames": frames}


def _visual_configuration(settings: Settings) -> tuple[str, str] | None:
    if settings.doubao_vision_endpoint and settings.doubao_vision_api_key:
        return settings.doubao_vision_endpoint, settings.doubao_vision_api_key
    if settings.doubao_llm_endpoint and settings.doubao_llm_api_key:
        return settings.doubao_llm_endpoint, settings.doubao_llm_api_key
    return None


def _send_vision_batch(
    batch: list[Path],
    batch_start: int,
    endpoint: str,
    api_key: str,
    settings: Settings,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": VISION_PROMPT}]
    for path in batch:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{_media_type(path)};base64,{_encode_image(path)}"},
            }
        )
    response: httpx.Response | None = None
    attempt_limit = min(max(settings.llm_max_attempts, 1), 3)
    for attempt in range(1, attempt_limit + 1):
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.doubao_llm_model,
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=90,
            )
            response.raise_for_status()
            break
        except httpx.HTTPStatusError as exc:
            retriable = exc.response.status_code == 429 or exc.response.status_code >= 500
            if not retriable or attempt == attempt_limit:
                return _failed_batch(
                    batch,
                    batch_start,
                    f"Visual understanding request failed with HTTP {exc.response.status_code}",
                )
        except httpx.RequestError as exc:
            if attempt == attempt_limit:
                return _failed_batch(
                    batch,
                    batch_start,
                    f"Visual understanding transport failed: {type(exc).__name__}",
                )
    try:
        if response is None:
            return _failed_batch(batch, batch_start, "Visual understanding request did not complete")
        payload = _response_json_object(response.json())
        raw_frames = payload.get("frames") if isinstance(payload, dict) else None
        if not isinstance(raw_frames, list):
            raise ValueError("Visual model did not return a frames array")
    except (ValueError, json.JSONDecodeError, TypeError, KeyError, IndexError):
        return _failed_batch(batch, batch_start, "Visual understanding returned invalid JSON")

    frames = [
        _normalize_frame(
            raw_frames[offset] if offset < len(raw_frames) and isinstance(raw_frames[offset], dict) else {},
            batch_start + offset + 1,
            path,
        )
        for offset, path in enumerate(batch)
    ]
    return {"status": "completed", "frames": frames}


def _response_json_object(payload: dict[str, Any]) -> dict[str, Any]:
    content: object = payload
    if "choices" in payload:
        content = payload["choices"][0].get("message", {}).get("content", "")
    elif "content" in payload:
        content = payload["content"]
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if isinstance(content, str):
        return _parse_json_content(content)
    if isinstance(content, dict):
        return content
    raise ValueError("Visual model response content is invalid")


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Visual model response is not a JSON object")
    return parsed


def _failed_batch(batch: list[Path], batch_start: int, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": error,
        "frames": [_placeholder_frame(batch_start + offset + 1, path) for offset, path in enumerate(batch)],
    }


def _normalize_frame(frame: dict[str, Any], index: int, path: Path) -> dict[str, Any]:
    description = str(frame.get("description") or "").strip()
    tags = [str(tag).strip() for tag in frame.get("tags", []) if str(tag).strip()]
    ocr = [str(text).strip() for text in frame.get("ocr", []) if str(text).strip()]
    colors = [str(color).strip() for color in frame.get("dominant_colors", []) if str(color).strip()]
    product_type = str(frame.get("product_type") or "").strip()
    return {
        "index": index,
        "path": str(path),
        "description": description or "Visual frame without description",
        "ocr": ocr,
        "tags": tags,
        "dominant_colors": colors,
        "product_type": product_type,
    }


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _media_type(path: Path) -> str:
    return {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "image/jpeg")


def _placeholder_frame(index: int, path: Path) -> dict[str, Any]:
    return {
        "index": index,
        "path": str(path),
        "description": "Key product or scene frame awaiting visual model analysis",
        "ocr": [],
        "tags": ["placeholder"],
        "dominant_colors": [],
    }
