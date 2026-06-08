"""Natural language structure editing — the P1-13 highlight feature.

Accepts a natural language command (e.g. "make the opening more grabby",
"shorten the proof section to 8 seconds", "swap product and CTA") and
returns an updated VideoStructure with a human-readable change summary.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from config import Settings
from models.schemas import VideoStructure
from services.llm_structure import DoubaoSeedClient, StructureExtractionError, _parse_json_content


NL_EDIT_PROMPT = """
You are StructForge's incremental structure editor. You translate the user's editing command into a minimal RFC 6902 JSON Patch that modifies ONLY what the user asked for.

## JSON Patch Format
Return a JSON array of patch operations. Each operation has:
- "op": "replace" | "add" | "remove" | "move"
- "path": JSON Pointer to the field to modify (e.g. "/script/0/copy")
- "value": the new value (for replace/add)

## JSON Pointer Path Construction Rules
The current VideoStructure has this structure. Paths MUST use these EXACT field names:
- /meta/duration, /meta/coverLabel - meta fields
- /script/N/copy - segment spoken text (N = 0-based index)
- /script/N/visual - segment visual description
- /script/N/duration - segment duration in seconds
- /script/N/camera - one of: 静态, 缓推, 快推, 拉远, 横移, 跟随, 手持微晃
- /script/N/pace - one of: 快, 正常, 慢
- /script/N/emotion - one of: 惊讶, 紧迫, 亲切, 权威, 感动, 兴奋, 平静
- /script/N/visual_fx - one of: 无, 震屏, 闪白, 慢动作, 放大, 模糊过渡
- /script/N/subtitle_anim - one of: 弹入, 淡入, 逐字出现, 缩放出现, 无动画
- /health/hook_strength, /health/overall, etc.

## Physical Parameter Mapping
- "开头更炸/更抓人" → /script/0/camera="快推", /script/0/visual_fx="震屏", /script/0/emotion="惊讶"
- "节奏太慢" → /script/N/pace="快", reduce /script/N/duration
- "不够高端" → rewrite /script/N/visual
- "结尾太弱" → /script/N/emotion="紧迫", /script/N/visual_fx="放大" (target last segment)
- "减少字幕" → /script/N/subtitle_anim="无动画"

## Few-Shot Examples

Example 1 — User: "开头更炸一点"
Current has script[0].camera="缓推", script[0].visual_fx="无", script[0].emotion="亲切"
Output:
[{{"op":"replace","path":"/script/0/camera","value":"快推"}},{{"op":"replace","path":"/script/0/visual_fx","value":"震屏"}},{{"op":"replace","path":"/script/0/emotion","value":"惊讶"}}]

Example 2 — User: "把结尾的紧迫感加强"
Current has 5 segments, script[4].type="cta", script[4].emotion="亲切", script[4].copy="快来买吧"
Output:
[{{"op":"replace","path":"/script/4/emotion","value":"紧迫"}},{{"op":"replace","path":"/script/4/visual_fx","value":"放大"}},{{"op":"replace","path":"/script/4/copy","value":"限时特惠！仅剩最后200单，手慢无！立即点击下方链接抢购"}}]

Example 3 — User: "产品信息提前"
Current script order: [0:hook, 1:pain, 2:product, 3:proof, 4:cta]
Output:
[{{"op":"move","path":"/script/1","from":"/script/2"}}]

## Rules
1. ONLY output the patch array — do NOT return the full structure.
2. Paths must match the EXACT structure shown above. Count segments from 0.
3. Wrap response as: {{"patch": <patch-array>, "changes_summary": "一句话中文描述做了哪些修改"}}
4. If you cannot express the change as a patch, return {{"patch": null, "changes_summary": "reason"}} and we'll fall back to full regeneration.

Current VideoStructure:
{structure_json}

User command: {command}
"""

NL_EDIT_FALLBACK_PROMPT = """
You are StructForge's structure editor. A user asked: "{command}"

The current structure is:
{structure_json}

Return ONLY a JSON object with "structure" (modified VideoStructure) and "changes_summary" (one Chinese sentence).
"""


class NLEditError(ValueError):
    """Raised when the NL edit cannot be completed."""


class NLEditorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def edit(self, structure: VideoStructure, command: str) -> tuple[VideoStructure, str]:
        """Apply a natural language edit command to the given structure.

        Tries RFC 6902 JSON Patch first (fast, token-efficient). Falls back
        to full structure regeneration if patch fails or LLM declines.

        Returns (updated_structure, changes_summary).
        """
        if not command.strip():
            raise NLEditError("编辑指令不能为空")

        if not self.settings.doubao_llm_endpoint or not self.settings.doubao_llm_api_key:
            raise NLEditError("LLM 未配置，无法执行自然语言编辑")

        client = DoubaoSeedClient(self.settings)
        structure_dict = structure.model_dump(mode="json", by_alias=True)
        structure_json = json.dumps(structure_dict, ensure_ascii=False, indent=2)

        prompt = NL_EDIT_PROMPT.format(structure_json=structure_json, command=command.strip())

        errors: list[str] = []
        for attempt in range(1, self.settings.llm_max_attempts + 1):
            try:
                raw = client.complete_json(prompt)
                if isinstance(raw, str):
                    raw = json.loads(raw)
                if not isinstance(raw, dict):
                    raise NLEditError("LLM 未返回有效的 JSON 对象")

                # ── Path A: JSON Patch (fast, incremental) ──
                patch = raw.get("patch")
                summary = str(raw.get("changes_summary", ""))
                if isinstance(patch, list) and len(patch) > 0:
                    try:
                        import jsonpatch
                        result_dict = jsonpatch.apply_patch(structure_dict, patch, in_place=False)
                        updated = VideoStructure.model_validate(result_dict)
                        return updated, summary or f"已通过增量补丁修改结构"
                    except (jsonpatch.JsonPatchException, Exception) as patch_err:
                        errors.append(f"Patch failed: {patch_err}")
                        # Fall through to Path B

                # ── Path B: Full structure (backward compatible) ──
                if "structure" in raw:
                    result_payload = raw["structure"]
                    updated = VideoStructure.model_validate(result_payload)
                    return updated, summary or f"已根据指令修改结构"

                # ── Path C: LLM returned something unexpected ──
                if patch is None:
                    # LLM explicitly declined to produce a patch
                    errors.append("LLM declined patch: " + summary)
                else:
                    raise NLEditError("LLM 返回的 JSON 缺少 structure 和 patch 字段")

            except (json.JSONDecodeError, ValidationError, StructureExtractionError) as exc:
                errors.append(str(exc))
                # On retry, simplify the prompt.
                prompt = NL_EDIT_FALLBACK_PROMPT.format(
                    command=command.strip(),
                    structure_json=structure_json,
                )

        raise NLEditError(
            f"自然语言编辑在 {self.settings.llm_max_attempts} 次尝试后失败: "
            + " | ".join(errors[-3:])
        )

    def edit_safe(
        self,
        structure_payload: dict[str, Any],
        command: str,
    ) -> tuple[dict[str, Any], str]:
        """Same as edit() but accepts raw dict and returns raw dict."""
        structure = VideoStructure.model_validate(structure_payload)
        updated, summary = self.edit(structure, command)
        return updated.model_dump(mode="json", by_alias=True), summary
