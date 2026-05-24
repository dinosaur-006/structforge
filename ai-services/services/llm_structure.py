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


PROMPT_TEMPLATE = """
You are StructForge's video structure analyst.

Return one strict JSON object that matches the frontend VideoStructure schema exactly.
Allowed top-level keys: meta, script, rhythm, packaging, health.
Do not use script_structure, rhythm_structure, packaging_structure, or health_scores.

Required schema:
{{
  "meta": {{"duration": number, "resolution": string, "shots": number, "coverLabel": string}},
  "script": [
    {{"id": string, "type": "hook|pain|product|proof|cta", "label": string,
      "start": number, "end": number, "duration": number, "goal": string,
      "copy": string, "visual": string, "healthScore": integer}}
  ],
  "rhythm": [{{"second": number, "cuts": integer, "emotion": number, "highlight": boolean}}],
  "packaging": {{"subtitleStyle": [string], "transitions": [string], "overlays": [string]}},
  "health": {{
    "hook_strength": integer,
    "product_exposure_timing": integer,
    "selling_point_proof": integer,
    "pacing_compactness": integer,
    "cta_persuasiveness": integer,
    "overall": integer
  }}
}}

Input context:
{context_json}
"""


class DoubaoSeedClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(self, prompt: str) -> object:
        if not self.settings.doubao_llm_endpoint or not self.settings.doubao_llm_api_key:
            raise StructureExtractionError("Doubao LLM is not configured")

        response = httpx.post(
            self.settings.doubao_llm_endpoint,
            headers={"Authorization": f"Bearer {self.settings.doubao_llm_api_key}"},
            json={
                "model": self.settings.doubao_llm_model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        content = _extract_content(payload)
        return _parse_json_content(content) if isinstance(content, str) else content


class LocalStructureClient:
    def __init__(self, prompt_context: dict[str, Any]) -> None:
        self.prompt_context = prompt_context

    def complete_json(self, prompt: str) -> object:
        return build_local_structure_payload(self.prompt_context)


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

    raise StructureExtractionError(
        f"LLM failed to return a valid frontend VideoStructure after {max_attempts} attempts: "
        + " | ".join(errors[-3:])
    )


def build_local_structure_payload(prompt_context: dict[str, Any]) -> dict[str, Any]:
    meta = prompt_context.get("meta", {})
    duration = float(meta.get("duration") or 35.0)
    resolution = str(meta.get("resolution") or "unknown")
    scenes = prompt_context.get("scenes") or []
    shots = len(scenes) if scenes else int(meta.get("shots") or 5)
    boundaries = _segment_boundaries(duration)

    script = [
        _segment("seg-1", "hook", "Hook", boundaries[0], boundaries[1], "stop_scroll", 84),
        _segment("seg-2", "pain", "Pain", boundaries[1], boundaries[2], "problem_framing", 72),
        _segment("seg-3", "product", "Product", boundaries[2], boundaries[3], "product_intro", 68),
        _segment("seg-4", "proof", "Proof", boundaries[3], boundaries[4], "selling_point_proof", 78),
        _segment("seg-5", "cta", "CTA", boundaries[4], boundaries[5], "conversion", 66),
    ]
    rhythm = _rhythm_points(duration, scenes)
    health = {
        "hook_strength": 84,
        "product_exposure_timing": 68,
        "selling_point_proof": 78,
        "pacing_compactness": 76,
        "cta_persuasiveness": 66,
        "overall": 74,
    }
    return {
        "meta": {
            "duration": duration,
            "resolution": resolution,
            "shots": shots,
            "coverLabel": "Generated keyframe cover",
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
    if len(structure.rhythm) >= 5:
        return structure
    payload = structure.model_dump(mode="json", by_alias=True)
    existing = payload.get("rhythm") or []
    by_second = {float(point["second"]): point for point in existing}
    duration = float(payload["meta"].get("duration") or 0)
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
