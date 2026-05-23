from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from config import Settings
from models.repository import SQLiteRepository
from models.schemas import FinalScript, FinalScriptStyle, VideoStructure
from services.gap_detector import GapDetector
from services.llm_structure import DoubaoSeedClient, JsonCompletionClient, StructureExtractionError


STYLE_INSTRUCTIONS: dict[str, str] = {
    "default": "保持原结构节奏，输出清晰、专业、可直接执行的分镜脚本。",
    "high_click": "强化前三秒冲突和停留理由，Hook 文案更短、更尖锐，字幕更醒目。",
    "high_conversion": "强化信任背书、优惠理由和 CTA 紧迫感，结尾转化动作更明确。",
    "fast_pace": "整体文案更短，镜头节奏更快，转场更紧凑，但总时长仍需匹配结构。",
    "high_quality": "文案更精致克制，画面描述增加光影、材质和高级感，转场更平滑。",
}


class MigrationNotFoundError(LookupError):
    pass


class MigrationInputError(ValueError):
    pass


class MigrationError(RuntimeError):
    pass


class MigratorService:
    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        settings: Settings | None = None,
        client: JsonCompletionClient | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or Settings()
        self.client = client or DoubaoSeedClient(self.settings)
        self.gap_detector = GapDetector(repository)

    def generate(self, project_id: str, style: FinalScriptStyle = "default") -> FinalScript:
        project = self.repository.get_project(project_id)
        if project is None:
            raise MigrationNotFoundError(f"Project not found: {project_id}")

        structure_payload = project.get("current_structure") or project.get("analysis_result")
        if not structure_payload:
            raise MigrationInputError("项目结构未初始化")
        structure = VideoStructure.model_validate(structure_payload)
        product_info, warnings = _product_info(project)
        assets = self.repository.list_assets(project_id)
        gaps = self.gap_detector.detect(project_id)
        prompt_context = {
            "project": {
                "id": project["id"],
                "name": project["name"],
                "product_info": product_info,
            },
            "style": style,
            "style_instruction": STYLE_INSTRUCTIONS[style],
            "structure": structure.model_dump(mode="json", by_alias=True),
            "assets": [_asset_summary(asset) for asset in assets],
            "gaps": gaps,
            "constraints": {
                "allowed_asset_ids": [asset["id"] for asset in assets],
                "total_duration": structure.meta.duration,
                "segment_count": len(structure.script),
            },
        }
        script = self._generate_with_retries(prompt_context, style, structure, assets, warnings)
        self.repository.save_project_script(project_id, script)
        return script

    def get_saved_script(self, project_id: str) -> FinalScript | None:
        if self.repository.get_project(project_id) is None:
            raise MigrationNotFoundError(f"Project not found: {project_id}")
        script = self.repository.get_project_script(project_id)
        return FinalScript.model_validate(script) if script else None

    def _generate_with_retries(
        self,
        prompt_context: dict[str, Any],
        style: str,
        structure: VideoStructure,
        assets: list[dict[str, Any]],
        base_warnings: list[str],
    ) -> FinalScript:
        errors: list[str] = []
        max_attempts = self.settings.llm_max_attempts
        for attempt in range(1, max_attempts + 1):
            try:
                prompt = _build_prompt(prompt_context, attempt)
                raw_payload = self.client.complete_json(prompt)
                if isinstance(raw_payload, str):
                    raw_payload = json.loads(raw_payload)
                script = FinalScript.model_validate(raw_payload)
                if script.version != style:
                    payload = script.model_dump(mode="json")
                    payload["version"] = style
                    script = FinalScript.model_validate(payload)
                return _normalize_script(script, structure, assets, base_warnings)
            except (json.JSONDecodeError, ValidationError, ValueError, StructureExtractionError) as exc:
                errors.append(str(exc))

        raise MigrationError(
            f"LLM failed to return a valid FinalScript after {max_attempts} attempts: "
            + " | ".join(errors[-3:])
        )


def _product_info(project: dict[str, Any]) -> tuple[str, list[str]]:
    description = str(project.get("description") or "").strip()
    if len("".join(description.split())) >= 10:
        return description, []

    name = str(project.get("name") or "").strip()
    unavailable = {"", "untitled", "untitled project", "未命名项目", "新建项目"}
    if name.lower() not in unavailable and not name.lower().startswith("proj-"):
        return name, ["商品信息来自项目名称，建议补充项目描述"]

    raise MigrationInputError("请补充商品信息")


def _asset_summary(asset: dict[str, Any]) -> dict[str, Any]:
    analysis = asset.get("analysis") or {}
    return {
        "id": asset["id"],
        "name": asset["name"],
        "type": asset["type"],
        "tag": asset["tag"],
        "match_status": asset["match_status"],
        "match_score": asset["match_score"],
        "description": analysis.get("description"),
        "tags": analysis.get("tags", []),
    }


def _build_prompt(context: dict[str, Any], attempt: int) -> str:
    payload = dict(context)
    payload["attempt"] = attempt
    return f"""
You are StructForge's structure migration and storyboard script generator.

Return one strict JSON object matching this FinalScript schema:
{{
  "version": "high_click|high_conversion|fast_pace|high_quality|default",
  "total_duration": number,
  "segments": [
    {{
      "id": string,
      "type": "hook|pain|product|proof|cta",
      "start": number,
      "end": number,
      "duration": number,
      "script": string,
      "visual": string,
      "asset_id": string|null,
      "subtitle_style": string,
      "transition": string,
      "locked": boolean
    }}
  ],
  "metadata": {{"warnings": [string], "generated_at": string}}
}}

Rules:
- Use only segment ids, timing, and segment types from the provided structure.
- Do not invent asset ids. Use an existing asset id or null.
- Keep total_duration within 10% of the provided structure duration.
- Generate polished Chinese short-video copy suitable for the product info.
- Apply the requested style instruction exactly.

Input context:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def _normalize_script(
    script: FinalScript,
    structure: VideoStructure,
    assets: list[dict[str, Any]],
    base_warnings: list[str],
) -> FinalScript:
    structure_duration = float(structure.meta.duration or sum(segment.duration for segment in structure.script))
    if structure_duration > 0:
        delta = abs(script.total_duration - structure_duration) / structure_duration
        if delta > 0.10:
            raise ValueError("FinalScript total_duration differs from structure duration by more than 10%")

    valid_asset_ids = {asset["id"] for asset in assets}
    payload = script.model_dump(mode="json")
    warnings = list(base_warnings)
    for segment in payload["segments"]:
        asset_id = segment.get("asset_id")
        if asset_id and asset_id not in valid_asset_ids:
            warnings.append(f"asset_id {asset_id} 不存在，已置为空")
            segment["asset_id"] = None

    metadata = dict(payload.get("metadata") or {})
    existing_warnings = metadata.get("warnings") or []
    if isinstance(existing_warnings, list):
        warnings = [*existing_warnings, *warnings]
    metadata["warnings"] = warnings
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    payload["metadata"] = metadata
    return FinalScript.model_validate(payload)
