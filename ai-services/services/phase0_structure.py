"""Phase 0: Dynamic video structure optimization — Material-Aware Edition.

Generates optimal segment structure via LLM based on product profile and
available user asset count, with 7 hard-coded constraint checks and a
defensive rule-based fallback safe net.

Architecture:
  - Zero assets (asset_count==0)  → 3-seg ultra-light (Hook→Product→CTA)
  - Light assets (1-3)            → 4-seg classic (Hook→Pain→Product→CTA)
  - Rich assets (>3)              → 5-8 seg high-pump trending structure
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from services.optimization_models import (
    DynamicStructure,
    PlatformType,
    ProductProfile,
    SegmentType,
    StructureSegment,
)

log = logging.getLogger("structforge.phase0")

# ── Allowed segment types ──
ALLOWED_SEGMENT_TYPES = frozenset({"hook", "pain", "product", "proof", "cta"})

# ── Subtitle detection ──
SUBTITLE_DETECTION_PROMPT = """Analyze the first {frame_count} keyframes of this video.
Do more than 70% of frames contain overlaid text (subtitles, captions, UI labels)?
Answer ONLY with one word: hard_sub, partial, or none."""


def detect_subtitle_type(
    video_path: str,
    vision_api_key: str,
    llm_endpoint: str,
    llm_model: str,
) -> Any:
    """Detect if the reference video has hard-coded subtitles."""
    from services.optimization_models import SubtitleType
    if not vision_api_key or not llm_endpoint:
        return SubtitleType.NONE
    try:
        # Quick probe using ffprobe to count frames with text
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        total_frames = int(result.stdout.strip() or "0")
        if total_frames < 10:
            return SubtitleType.NONE

        # Sample a few frames and ask Vision model
        frame_count = min(5, total_frames)
        prompt = SUBTITLE_DETECTION_PROMPT.format(frame_count=frame_count)
        response = httpx.post(
            llm_endpoint,
            headers={"Authorization": f"Bearer {vision_api_key}"},
            json={
                "model": llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 16,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        content = ""
        if "choices" in payload:
            content = payload["choices"][0].get("message", {}).get("content", "")
        answer = str(content).strip().lower()
        if "hard_sub" in answer:
            return SubtitleType.HARD_SUB
        if "partial" in answer:
            return SubtitleType.PARTIAL
        return SubtitleType.NONE
    except Exception:
        return SubtitleType.NONE


# ══════════════════════════════════════════════════════════════════════════
# Structure Optimizer — Material-Aware Dynamic Planning
# ══════════════════════════════════════════════════════════════════════════

class StructureOptimizer:
    """Generate optimal video structure with material-aware planning.

    Usage:
        optimizer = StructureOptimizer(llm_endpoint, llm_api_key, llm_model)
        structure = optimizer.generate(product, user_asset_count=0)
    """

    def __init__(
        self,
        llm_endpoint: str,
        llm_api_key: str,
        llm_model: str = "doubao-seed-2-0-lite",
    ) -> None:
        self._endpoint = llm_endpoint
        self._api_key = llm_api_key
        self._model = llm_model
        self._available = bool(llm_endpoint and llm_api_key)

    @property
    def available(self) -> bool:
        return self._available

    def generate(
        self,
        product: ProductProfile,
        user_asset_count: int = 0,
    ) -> DynamicStructure:
        """Generate optimal segment structure based on product and asset availability.

        Args:
            product: Product profile with name, type, selling points.
            user_asset_count: Number of user-uploaded assets available.

        Returns:
            DynamicStructure with validated segments ready for downstream use.
        """
        log.info(
            "Phase 0: material-aware planning — product=%s, assets=%d",
            product.name, user_asset_count,
        )

        if not self._available:
            log.warning("Phase 0: LLM unavailable, using fallback structure")
            return _build_fallback_structure(product, user_asset_count)

        system_prompt = _build_material_aware_prompt(user_asset_count)
        user_content = (
            f"产品名称: {product.name}\n"
            f"产品类型: {product.product_type.value}\n"
            f"核心卖点: {', '.join(product.selling_points) if product.selling_points else '未提供'}\n"
            f"目标受众: {product.target_audience or '大众消费者'}\n"
            f"优惠信息: {product.offer or '未提供'}\n"
            f"表达语气: {product.tone or '专业亲切'}\n"
            f"平台: {product.platform.value}\n\n"
            f"请立即针对该产品构建最优分镜结构线。"
        )

        for attempt in range(1, 4):
            try:
                response = httpx.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "max_tokens": 1024,
                        "temperature": 0.3,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
                content = ""
                if "choices" in payload:
                    content = payload["choices"][0].get("message", {}).get("content", "")
                if not content:
                    raise ValueError("LLM returned empty response")

                # Parse JSON from response
                raw = json.loads(_extract_json(content))
                segments_data = raw.get("segments", [])
                if not segments_data:
                    raise ValueError("LLM returned no segments")

                # Build segments
                segments = []
                for i, seg in enumerate(segments_data):
                    seg_type_str = str(seg.get("type", "product")).lower()
                    if seg_type_str not in ALLOWED_SEGMENT_TYPES:
                        seg_type_str = "product"
                    segments.append(StructureSegment(
                        id=seg.get("id", f"seg_{i+1:02d}"),
                        type=SegmentType(seg_type_str),
                        label=str(seg.get("label", "")),
                        target_duration=float(seg.get("duration", 4.0)),
                        screen_subtitle=str(seg.get("screen_subtitle", "")),
                        tts_script=str(seg.get("tts_script", seg.get("screen_subtitle", ""))),
                        visual_description=str(seg.get("visual_description", "")),
                        ai_prompt=str(seg.get("ai_prompt", "")),
                    ))

                structure = DynamicStructure(
                    segments=segments,
                    strategy=str(raw.get("structure_strategy", "llm-generated")),
                    total_duration=float(raw.get("total_duration", sum(s.target_duration for s in segments))),
                )

                # ── 7 hard constraint checks ──
                if _validate_constraints(structure):
                    log.info("Phase 0: structure passed all 7 constraints")
                    return structure

                log.warning("Phase 0: LLM output failed constraints, retrying...")
            except Exception as exc:
                log.warning("Phase 0 attempt %d failed: %s", attempt, exc)

        # All attempts exhausted — fallback
        log.warning("Phase 0: all LLM attempts failed, using fallback structure")
        return _build_fallback_structure(product, user_asset_count)


# ══════════════════════════════════════════════════════════════════════════
# Material-Aware Prompt Builder
# ══════════════════════════════════════════════════════════════════════════

def _build_material_aware_prompt(asset_count: int) -> str:
    """Build system prompt that adapts structure complexity to available assets."""
    base = (
        "你是 StructForge 的顶层结构架构师。你负责在新产品创作开始前，规划出最科学的视频槽位骨架。\n"
        "你必须输出且只能输出一个合法的 JSON 对象，不要包含任何 Markdown 格式标记。\n\n"
        "【7项硬性防线指标】：\n"
        "1. 总建议时长 total_duration 必须严格在 18.0 至 30.0 秒之间。\n"
        "2. 第一个分镜的 type 必须是 'hook'，且其建议时长 duration 必须 <= 3.0 秒。\n"
        "3. 最后一个分镜的 type 必须是 'cta'，且其建议时长 duration 必须 <= 4.0 秒。\n"
        "4. 结构总段数只能在 3 到 8 段之间。\n"
        "5. 每个单段分镜建议时长必须 >= 1.0 秒。\n"
        "6. 所有分镜建议时长的总和必须等同于外层的 total_duration。\n"
        "7. 分镜的 type 只能在 ['hook', 'pain', 'product', 'proof', 'cta'] 白名单中选择。\n\n"
    )

    if asset_count == 0:
        strategy = (
            "【素材态势感知：零素材空盘状态】\n"
            "当前用户没有提供任何视频和图片素材！为防止结构太长导致画面崩塌为纯字幕卡片，你必须：\n"
            "- 强行采用【3段式超轻量剪辑方案】：Hook -> Product -> CTA。\n"
            "- 所有的 visual_description 必须写得极其适合 AIGC 100% 稳定生成。\n"
            "- 倾向于生成静态高奢物品微距空镜（如：精致的瓶身特写，暗色背景上的柔光反射）。\n"
            "- 绝对禁止规划复杂的真人行为、特定达人面对镜头大哭等高难度画面！\n"
            "- 输出格式: {{\"segments\":[{{\"id\":\"seg_01\",\"type\":\"hook\",\"label\":\"...\","
            "\"duration\":3.0,\"screen_subtitle\":\"...\",\"tts_script\":\"...\","
            "\"visual_description\":\"...\",\"ai_prompt\":\"...\"}}],"
            "\"total_duration\":20.0,\"structure_strategy\":\"3-SEG-ZERO-ASSET\"}}\n"
        )
    elif 1 <= asset_count <= 3:
        strategy = (
            "【素材态势感知：轻度素材状态】\n"
            "用户提供了 1-3 张基础素材。你可以分配它们填入对应的核心卡槽，采用【4段式经典说服结构】：\n"
            "- 规划为 Hook(开头吸引) -> Pain(痛点放大) -> Product(产品引入) -> CTA(转化号召)。\n"
            "- 在 visual_description 中，将痛点和产品镜头与用户的实拍素材靠拢。\n"
            "- 输出格式: 同上，structure_strategy 标记为 '4-SEG-BALANCED'\n"
        )
    else:
        strategy = (
            "【素材态势感知：富裕素材状态】\n"
            "用户素材非常充足！立刻释放全部剪辑潜力，允许放开限制，生成 5 至 8 段的爆款MCN高阶切镜结构：\n"
            "- 推荐加入 Proof(多维卖点拆解对比) 镜头，将节奏点加密。\n"
            "- 每个分镜要利用好丰富的物理镜头变化描述。\n"
            "- 输出格式: 同上，structure_strategy 标记为 '5-8-SEG-HIGH-PUMP'\n"
        )

    return base + strategy


# ══════════════════════════════════════════════════════════════════════════
# 7 Hard Constraint Validator
# ══════════════════════════════════════════════════════════════════════════

def _validate_constraints(structure: DynamicStructure) -> bool:
    """Check all 7 hard constraints. Returns True if all pass."""
    try:
        segments = structure.segments
        count = len(segments)

        # 1: 3-8 segments
        if not (3 <= count <= 8):
            log.error("Constraint 1 FAIL: segment count=%d (need 3-8)", count)
            return False

        # 2: total duration 18-30s
        if not (18.0 <= structure.total_duration <= 30.0):
            log.error("Constraint 2 FAIL: total_duration=%.1f (need 18-30)", structure.total_duration)
            return False

        # 3: first must be hook, last must be cta
        if segments[0].type.value != "hook" or segments[-1].type.value != "cta":
            log.error(
                "Constraint 3 FAIL: first=%s (need hook), last=%s (need cta)",
                segments[0].type.value, segments[-1].type.value,
            )
            return False

        # 4: hook <= 3s
        if segments[0].target_duration > 3.0:
            log.error("Constraint 4 FAIL: hook duration=%.1f (need <=3s)", segments[0].target_duration)
            return False

        # 5: cta <= 4s
        if segments[-1].target_duration > 4.0:
            log.error("Constraint 5 FAIL: cta duration=%.1f (need <=4s)", segments[-1].target_duration)
            return False

        # 6: each segment >= 1s, sum matches total
        duration_sum = 0.0
        for seg in segments:
            if seg.target_duration < 1.0:
                log.error("Constraint 6 FAIL: segment %s duration=%.1f (need >=1s)", seg.id, seg.target_duration)
                return False
            duration_sum += seg.target_duration

        if abs(duration_sum - structure.total_duration) > 0.1:
            log.warning(
                "Constraint 7 WARN: duration sum mismatch (sum=%.2f, total=%.2f), auto-correcting",
                duration_sum, structure.total_duration,
            )
            structure.total_duration = round(duration_sum, 2)

        return True
    except Exception as exc:
        log.error("Constraint validation crashed: %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════
# Defensive Fallback — Rule-Based Safe Structure
# ══════════════════════════════════════════════════════════════════════════

def _build_fallback_structure(
    product: ProductProfile,
    asset_count: int,
) -> DynamicStructure:
    """Build a safe, rule-based structure when LLM is unavailable or fails."""
    log.warning("Phase 0: defensive fallback engaged — asset_count=%d", asset_count)

    if asset_count == 0:
        # 3-seg ultra-light for zero-asset scenarios
        segments = [
            StructureSegment(
                id="fb_seg_01", type=SegmentType("hook"), label="开头冲击",
                target_duration=3.0,
                screen_subtitle=f"发现了一款神奇的{product.name}",
                tts_script=f"你敢相信吗？这款{product.name}真的太绝了！",
                visual_description="精致的瓶身特写，暗色背景上的柔光反射，电影级慢推进",
                ai_prompt="A crisp studio macro close-up focusing on high-end product exterior, cinematic slow push-in, bright key light on dark background.",
            ),
            StructureSegment(
                id="fb_seg_02", type=SegmentType("product"), label="产品引入",
                target_duration=8.0,
                screen_subtitle=" ".join(product.selling_points[:2]) if product.selling_points else "品质之选",
                tts_script=f"{product.name}，{'、'.join(product.selling_points[:3]) if product.selling_points else '品质超乎想象'}，买它就对了。",
                visual_description="产品居中展示，镜面反射材质，体积光柔光包裹，8K高清细节",
                ai_prompt="Product center framed on mirror surface, volumetric luxury light, slow panning shot showing 8k premium texture.",
            ),
            StructureSegment(
                id="fb_seg_03", type=SegmentType("cta"), label="立即行动",
                target_duration=4.0,
                screen_subtitle="限量优惠，手慢无！",
                tts_script=f"还在等什么？{product.name}限时优惠，点击下方链接，马上入手！",
                visual_description="动态图形文字框，强烈聚焦，工作室柔光，直接高冲击定位",
                ai_prompt="Dynamic motion graphics frame with intense focus, studio soft light, direct high-impact positioning.",
            ),
        ]
        strategy = "FALLBACK-3-SEG-ZERO-ASSET"
        total = 15.0
    else:
        # 4-seg classic for any non-zero asset scenario
        sp1 = product.selling_points[0] if product.selling_points else "卓越品质"
        sp2 = product.selling_points[1] if len(product.selling_points) > 1 else "超乎想象"
        segments = [
            StructureSegment(
                id="fb_seg_01", type=SegmentType("hook"), label="开头冲击",
                target_duration=3.0,
                screen_subtitle=f"你是不是也遇到过？",
                tts_script=f"你是不是也一直被这个问题困扰？今天给你看一个神器——{product.name}！",
                visual_description="达人震惊捂嘴特写，快速冲镜，高对比戏剧光",
                ai_prompt="Shocked expression close-up, dramatic spotlight, fast camera zoom-in.",
            ),
            StructureSegment(
                id="fb_seg_02", type=SegmentType("pain"), label="痛点场景",
                target_duration=5.0,
                screen_subtitle="别再忍受了！",
                tts_script=f"每次遇到这个问题都很烦对吧？其实解决方案就在这里。",
                visual_description="真实使用场景，侧光高对比，模糊背景强调细节",
                ai_prompt="Realistic scenario shot with dramatic side light, blurry background emphasizing subtle details.",
            ),
            StructureSegment(
                id="fb_seg_03", type=SegmentType("product"), label="产品引入",
                target_duration=8.0,
                screen_subtitle=f"{sp1} + {sp2}",
                tts_script=f"{product.name}，{sp1}，{sp2}，用过的人都说好。",
                visual_description="产品英雄镜头，奢华体积光，4K微距旋转展示",
                ai_prompt="Hero product shot, luxury volumetric lighting, 4k macro rotation display.",
            ),
            StructureSegment(
                id="fb_seg_04", type=SegmentType("cta"), label="立即行动",
                target_duration=4.0,
                screen_subtitle="限时优惠，手慢无",
                tts_script=f"别犹豫了，{product.name}限时优惠中，点击下方马上入手！",
                visual_description="动态图形，紧迫感红点闪烁，直接高冲击定位",
                ai_prompt="Dynamic motion graphics with urgent red pulse, direct high-impact call to action.",
            ),
        ]
        strategy = "FALLBACK-4-SEG-CLASSIC"
        total = 20.0

    return DynamicStructure(segments=segments, strategy=strategy, total_duration=total)


# ══════════════════════════════════════════════════════════════════════════
# Legacy compatibility — validate_structure, build_structure_prompt
# ══════════════════════════════════════════════════════════════════════════

def validate_structure(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a structure dict against hard constraints. Returns (valid, errors)."""
    errors: list[str] = []
    segments = data.get("segments", [])
    if not (3 <= len(segments) <= 8):
        errors.append(f"段数 {len(segments)} 不在3-8范围内")
    total_dur = float(data.get("total_duration", 0))
    if not (18 <= total_dur <= 30):
        errors.append(f"总时长 {total_dur}s 不在18-30s内")
    if segments:
        if segments[0].get("type") != "hook":
            errors.append("首段不是hook")
        if segments[-1].get("type") != "cta":
            errors.append("末段不是cta")
        if float(segments[0].get("target_duration", 0)) > 3:
            errors.append("Hook超过3秒")
        for seg in segments:
            t = seg.get("type", "")
            if t not in ALLOWED_SEGMENT_TYPES:
                errors.append(f"非法类型: {t}")
    return len(errors) == 0, errors


def build_structure_prompt(product: ProductProfile) -> str:
    """Build a user prompt for structure generation (legacy compatibility)."""
    return (
        f"产品名称: {product.name}\n"
        f"产品类型: {product.product_type.value}\n"
        f"卖点: {', '.join(product.selling_points) if product.selling_points else '未提供'}\n"
        f"受众: {product.target_audience or '大众'}\n"
        f"请生成最优结构。"
    )


def _extract_json(content: str) -> str:
    """Extract JSON object from LLM response text."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3]
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return content[start:end + 1]
    return content
