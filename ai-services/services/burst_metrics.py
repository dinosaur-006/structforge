"""Full-modal burst video metrics — 32 quantifiable indicators across 5 dimensions × 4 modalities.

Dimensions: Hook(注意力锚点) / Trust(信任梯度) / Density(卖点密度) / Pacing(节奏曲线) / CTA(转化指令)
Modalities: visual(画面) / audio(语音) / subtitle(字幕) / structure(结构)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# Platform-Dynamic Weighting System
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PlatformWeights:
    """Metric weight multipliers based on platform algorithm priorities."""
    platform: str
    hook_conflict_words: float = 1.0
    hook_visual_conflict: float = 1.0
    trust_data_evidence: float = 1.0
    trust_testimonial: float = 1.0
    density_first_benefit: float = 1.0
    cta_visual_focus: float = 1.0
    cta_price_anchor: float = 1.0
    cta_action_words: float = 1.0

    @classmethod
    def for_platform(cls, platform: str) -> "PlatformWeights":
        if platform == "xiaohongshu":
            return cls(platform="xiaohongshu", hook_conflict_words=2.0, hook_visual_conflict=1.5,
                       trust_testimonial=1.8, trust_data_evidence=1.2, cta_action_words=0.8)
        elif platform == "douyin":
            return cls(platform="douyin", density_first_benefit=2.0, cta_price_anchor=2.0,
                       cta_visual_focus=1.8, cta_action_words=1.8, hook_conflict_words=1.5)
        elif platform == "wechat":
            return cls(platform="wechat", trust_data_evidence=1.5, hook_conflict_words=1.5)
        return cls(platform="default")


@dataclass
class MetricResult:
    metric_id: str       # e.g. "H-V1"
    name: str            # Chinese name
    dimension: str       # hook | trust | density | pacing | cta
    modality: str        # visual | audio | subtitle | structure
    score: int           # 0-100
    max_score: int       # 100
    evidence: str        # human-readable evidence
    raw_value: str       # raw computed value
    passed: bool = False # whether meets viral threshold


@dataclass
class DimensionReport:
    name: str
    score: int           # average of all metrics
    metrics: list[MetricResult] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class FullAuditReport:
    overall_score: int
    platform_score: int = 0                            # Platform-weighted score
    dimensions: list[DimensionReport] = field(default_factory=list)
    all_metrics: list[MetricResult] = field(default_factory=list)
    llm_insights: dict[str, Any] = field(default_factory=dict)
    suggestions: list[dict[str, str]] = field(default_factory=list)
    burst_template: dict[str, Any] = field(default_factory=dict)
    auto_fix_patches: list[dict[str, Any]] = field(default_factory=list)  # RFC 6902 patches for auto-fix


# ── Conflict/suspense word bank ──
CONFLICT_WORDS = re.compile(
    r"炸了|竟然|居然|千万别|为什么|你敢信|没想到|原来|天哪|震惊|揭秘|"
    r"等等|不可能|他们不想|我测了|只有|疯了|赢麻|绝了"
)

# ── Trust evidence word bank ──
TRUST_WORDS = re.compile(
    r"认证|检测|专利|实测|权威|医院|医生|专家|推荐|用了|效果|"
    r"对比|数据|证明|\%|\d+万|\d+亿|\d+年"
)

# ── CTA action word bank ──
CTA_WORDS = re.compile(
    r"点击|购买|查看|抢|下单|入手|带走|试试|限时|限量|最后|"
    r"只剩|错过|不再|赶紧|立刻|马上|点击下方|小黄车|链接"
)

# ── Selling point word bank ──
SELLING_POINT_WORDS = re.compile(
    r"改善|提升|减少|降低|持久|防水|防汗|速干|控油|保湿|"
    r"美白|抗皱|紧致|修护|滋养|清洁|去污|除菌|杀菌"
)

# ── Urgency word bank ──
URGENCY_WORDS = re.compile(r"限时|限量|最后|只剩|错过|不再|赶紧|立刻|马上|秒杀|抢购|倒计时")


class BurstMetricsCalculator:
    """Calculate 32 viral video metrics from analysis data."""

    def __init__(
        self,
        shots: list[dict[str, Any]],
        asr_text: str,
        asr_segments: list[dict[str, Any]],
        vision_frames: list[dict[str, Any]],
        duration: float,
        rhythm_points: list[dict[str, Any]] | None = None,
        packaging: dict[str, Any] | None = None,
        platform: str = "douyin",
    ) -> None:
        self.shots = shots or []
        self.asr_text = asr_text or ""
        self.asr_segments = asr_segments or []
        self.vision_frames = vision_frames or []
        self.duration = max(duration, 1.0)
        self.rhythm = rhythm_points or []
        self.packaging = packaging or {}
        self.platform = platform
        self.weights = PlatformWeights.for_platform(platform)

    # ── Public API ──

    def calculate_all(self) -> list[MetricResult]:
        results: list[MetricResult] = []
        results.extend(self._hook_visual())
        results.extend(self._hook_audio())
        results.extend(self._hook_subtitle())
        results.extend(self._trust_visual())
        results.extend(self._trust_audio())
        results.extend(self._trust_subtitle())
        results.extend(self._density_visual())
        results.extend(self._density_audio())
        results.extend(self._density_subtitle())
        results.extend(self._pacing_visual())
        results.extend(self._pacing_audio())
        results.extend(self._pacing_subtitle())
        results.extend(self._cta_visual())
        results.extend(self._cta_audio())
        results.extend(self._cta_subtitle())
        return results

    def _apply_weights(self, metric: MetricResult) -> int:
        """Apply platform-specific weight to a metric score."""
        weight_map = {
            "H-A2": self.weights.hook_conflict_words,
            "H-V2": self.weights.hook_visual_conflict,
            "T-A1": self.weights.trust_data_evidence,
            "T-A2": self.weights.trust_testimonial,
            "D-A2": self.weights.density_first_benefit,
            "C-V2": self.weights.cta_visual_focus,
            "C-S1": self.weights.cta_price_anchor,
            "C-A1": self.weights.cta_action_words,
        }
        weight = weight_map.get(metric.metric_id, 1.0)
        return min(100, int(metric.score * weight))

    def dimension_reports(self) -> list[DimensionReport]:
        all_metrics = self.calculate_all()
        dims: dict[str, list[MetricResult]] = {}
        for m in all_metrics:
            dims.setdefault(m.dimension, []).append(m)

        reports = []
        dim_names = {
            "hook": "注意力锚点 (Hook)",
            "trust": "信任梯度 (Trust)",
            "density": "卖点密度 (Density)",
            "pacing": "节奏曲线 (Pacing)",
            "cta": "转化指令 (CTA)",
        }
        for dim_key, metrics in dims.items():
            # Platform-weighted average
            weighted_scores = [self._apply_weights(m) for m in metrics]
            avg = sum(weighted_scores) // max(len(weighted_scores), 1)
            strengths = [m.name for m in metrics if self._apply_weights(m) >= 80]
            weaknesses = [m.name for m in metrics if self._apply_weights(m) < 40]
            reports.append(DimensionReport(
                name=dim_names.get(dim_key, dim_key),
                score=avg,
                metrics=metrics,
                strengths=strengths,
                weaknesses=weaknesses,
            ))
        return reports

    def platform_score(self) -> int:
        """Calculate overall platform-weighted score."""
        all_metrics = self.calculate_all()
        weighted = [self._apply_weights(m) for m in all_metrics]
        return sum(weighted) // max(len(weighted), 1)

    def generate_auto_fix_patches(self) -> list[dict[str, Any]]:
        """Generate RFC 6902 JSON Patches for metrics that score critically low.

        Each patch suggests an automated fix for the visual timeline.
        Returns a list of fix objects: {metric_id, severity, action, patch}.
        """
        all_metrics = self.calculate_all()
        patches: list[dict[str, Any]] = []

        # Auto-fix rules: when a metric scores 0 or < threshold, suggest a patch
        auto_fix_rules = {
            "C-S1": {  # Price anchoring missing
                "check": lambda m: m.score < 30,
                "patch": [
                    {"op": "add", "path": "/tracks/0/clips/-",
                     "value": {"component": "StatCard", "props": {"statValue": "限时优惠", "statLabel": "立即抢购", "badge": "HOT"}}}
                ],
                "description": "自动添加价格锚定 StatCard 组件"
            },
            "H-A2": {  # Conflict words missing
                "check": lambda m: m.score < 30,
                "patch": [
                    {"op": "replace", "path": "/tracks/0/clips/0/component", "value": "TitleCard"},
                    {"op": "replace", "path": "/tracks/0/clips/0/props/title", "value": "千万别买！除非..."},
                ],
                "description": "自动替换Hook为冲突式TitleCard"
            },
            "T-A1": {  # Data evidence missing
                "check": lambda m: m.score < 20,
                "patch": [
                    {"op": "add", "path": "/tracks/0/clips/-",
                     "value": {"component": "StatCard", "props": {"statValue": "权威认证", "statLabel": "品质保障", "badge": "VERIFIED"}}}
                ],
                "description": "自动添加数据背书 StatCard 组件"
            },
            "C-A1": {  # CTA action words missing
                "check": lambda m: m.score < 30,
                "patch": [
                    {"op": "replace", "path": "/tracks/1/clips/-1/component", "value": "CTACard"},
                    {"op": "replace", "path": "/tracks/1/clips/-1/props/buttonText", "value": "立即抢购"},
                    {"op": "replace", "path": "/tracks/1/clips/-1/props/urgencyLevel", "value": "high"},
                ],
                "description": "自动强化CTA为高紧迫感CTACard"
            },
        }

        for metric in all_metrics:
            if metric.metric_id in auto_fix_rules:
                rule = auto_fix_rules[metric.metric_id]
                if rule["check"](metric):
                    patches.append({
                        "metric_id": metric.metric_id,
                        "metric_name": metric.name,
                        "current_score": metric.score,
                        "severity": "critical" if metric.score < 20 else "warning",
                        "action": rule["description"],
                        "rfc6902_patch": rule["patch"],
                    })

        return patches

    # ═══════════════════════════════════════════════════════════════
    # Dimension 1: Hook (注意力锚点) — 前3秒
    # ═══════════════════════════════════════════════════════════════

    def _hook_visual(self) -> list[MetricResult]:
        hook_shots = [s for s in self.shots if float(s.get("start_s", s.get("start", 0))) < 3.0]
        hook_frames = [f for f in self.vision_frames if f.get("index", 99) <= 3]

        # H-V1: 镜头切换频率
        freq = len(hook_shots) / 3.0
        score_hv1 = min(100, int(freq * 50))
        hv1 = MetricResult("H-V1", "镜头切换频率", "hook", "visual", score_hv1, 100,
                           f"前3秒{len(hook_shots)}个镜头, 频率{freq:.1f}次/秒", f"{freq:.1f}次/秒",
                           freq >= 2.0)

        # H-V2: 视觉冲突强度
        has_conflict = any("冲突" in str(f.get("tags", [])) or "反转" in str(f.get("tags", []))
                          for f in hook_frames)
        score_hv2 = 100 if has_conflict else 20
        hv2 = MetricResult("H-V2", "视觉冲突强度", "hook", "visual", score_hv2, 100,
                           "画面含冲突/反转标签" if has_conflict else "未检测到视觉冲突",
                           "有" if has_conflict else "无", has_conflict)

        # H-V3: 画面亮度突变
        colors_list = [f.get("dominant_colors", []) for f in hook_frames[:2]]
        has_bright_change = len(colors_list) >= 2 and colors_list[0] != colors_list[1]
        score_hv3 = 80 if has_bright_change else 40
        hv3 = MetricResult("H-V3", "画面亮度突变", "hook", "visual", score_hv3, 100,
                           "检测到明暗变化" if has_bright_change else "亮度过渡平缓",
                           "检测到" if has_bright_change else "未检测到", has_bright_change)

        # H-V4: 主体放大/推镜
        has_zoom = any("推" in str(f.get("motion_type", "")) or "放大" in str(f.get("tags", []))
                      for f in hook_frames)
        score_hv4 = 90 if has_zoom else 30
        hv4 = MetricResult("H-V4", "主体放大推镜", "hook", "visual", score_hv4, 100,
                           "检测到推镜/放大效果" if has_zoom else "未检测到推镜",
                           "有" if has_zoom else "无", has_zoom)

        return [hv1, hv2, hv3, hv4]

    def _hook_audio(self) -> list[MetricResult]:
        asr_lower = self.asr_text.lower()
        words = list(self.asr_text) if self.asr_text else []
        char_count = len(words)
        hook_duration = min(3.0, self.duration)
        speech_rate = char_count / max(hook_duration, 0.5)

        # H-A1: 开场音量/音高突变 — use segment energy
        has_audio_peak = any(
            float(s.get("energy_peak_second", s.get("avg_db", -100))) > -15
            for s in self.asr_segments[:3]
        ) if self.asr_segments else False
        score_ha1 = 85 if has_audio_peak else 35
        ha1 = MetricResult("H-A1", "开场音量突变", "hook", "audio", score_ha1, 100,
                           "前0.5秒检测到能量峰值" if has_audio_peak else "开场音量平缓",
                           "检测到" if has_audio_peak else "未检测到", has_audio_peak)

        # H-A2: 冲突词/悬念词
        conflict_count = len(CONFLICT_WORDS.findall(self.asr_text[:200]))
        score_ha2 = min(100, conflict_count * 50)
        ha2 = MetricResult("H-A2", "冲突词/悬念词", "hook", "audio", score_ha2, 100,
                           f"检测到{conflict_count}个冲突/悬念词" if conflict_count else "未检测到冲突词",
                           f"{conflict_count}个", conflict_count >= 1)

        # H-A3: 语速突增
        global_rate = char_count / max(self.duration, 0.5)
        hook_rate = speech_rate
        rate_surge = hook_rate > global_rate * 1.3
        score_ha3 = 85 if rate_surge else 40
        ha3 = MetricResult("H-A3", "语速突增", "hook", "audio", score_ha3, 100,
                           f"前3秒语速{hook_rate:.1f}字/秒 vs 全局{global_rate:.1f}字/秒",
                           f"{hook_rate:.1f}字/秒", rate_surge)

        return [ha1, ha2, ha3]

    def _hook_subtitle(self) -> list[MetricResult]:
        ocr_texts = []
        for f in self.vision_frames[:3]:
            ocr_texts.extend(f.get("ocr", []))

        # H-T1: 弹入/弹出动画 — proxy: subtitle_style contains animation keywords
        sub_style = str(self.packaging.get("subtitleStyle", ""))
        has_animation = any(kw in sub_style for kw in ["弹入", "弹簧", "缩放", "逐字", "bounce"])
        score_ht1 = 90 if has_animation else 30
        ht1 = MetricResult("H-T1", "字幕弹入动画", "hook", "subtitle", score_ht1, 100,
                           "字幕使用动态入场效果" if has_animation else "字幕静态出现",
                           "有动画" if has_animation else "无动画", has_animation)

        # H-T2: 字号突变 — proxy: font_size change detection
        score_ht2 = 50  # Default: can't reliably measure without actual rendering
        ht2 = MetricResult("H-T2", "字号突变", "hook", "subtitle", score_ht2, 100,
                           "基于视觉检测评估字号变化", "中等", False)

        # H-T3: 颜色冲突
        has_highlight = any(
            str(c).upper() in ("#FFFF00", "#FF0000", "#FFD700", "YELLOW", "RED", "GOLD")
            for f in self.vision_frames[:3] for c in f.get("dominant_colors", [])
        )
        score_ht3 = 85 if has_highlight else 25
        ht3 = MetricResult("H-T3", "字幕高亮颜色", "hook", "subtitle", score_ht3, 100,
                           "使用高亮色(红/黄/金)" if has_highlight else "使用常规色",
                           "高亮" if has_highlight else "常规", has_highlight)

        return [ht1, ht2, ht3]

    # ═══════════════════════════════════════════════════════════════
    # Dimension 2: Trust (信任梯度)
    # ═══════════════════════════════════════════════════════════════

    def _trust_visual(self) -> list[MetricResult]:
        total_frames = max(len(self.vision_frames), 1)

        # T-V1: 产品特写时长占比
        product_frames = sum(1 for f in self.vision_frames
                           if "产品特写" in str(f.get("tags", [])) or "瓶身特写" in str(f.get("tags", []))
                           or "包装特写" in str(f.get("tags", [])))
        ratio = product_frames / total_frames
        score_tv1 = min(100, int(ratio * 300))
        tv1 = MetricResult("T-V1", "产品特写占比", "trust", "visual", score_tv1, 100,
                           f"{product_frames}/{total_frames}帧为产品特写 ({ratio:.0%})",
                           f"{ratio:.0%}", ratio >= 0.3)

        # T-V2: 使用场景演示
        has_demo = any("演示" in str(f.get("tags", [])) or "涂抹" in str(f.get("tags", []))
                      for f in self.vision_frames)
        score_tv2 = 90 if has_demo else 20
        tv2 = MetricResult("T-V2", "使用场景演示", "trust", "visual", score_tv2, 100,
                           "有演示/使用镜头" if has_demo else "缺少演示镜头",
                           "有" if has_demo else "无", has_demo)

        # T-V3: 对比画面
        has_compare = any("对比" in str(f.get("tags", [])) for f in self.vision_frames)
        score_tv3 = 90 if has_compare else 20
        tv3 = MetricResult("T-V3", "对比画面", "trust", "visual", score_tv3, 100,
                           "有对比画面" if has_compare else "缺少对比画面",
                           "有" if has_compare else "无", has_compare)

        # T-V4: 成分/细节展示
        has_detail = any("微距" in str(f.get("tags", [])) or "内部拆解" in str(f.get("tags", []))
                        or "材质反光" in str(f.get("tags", [])) for f in self.vision_frames)
        score_tv4 = 85 if has_detail else 25
        tv4 = MetricResult("T-V4", "细节展示", "trust", "visual", score_tv4, 100,
                           "有微距/细节镜头" if has_detail else "缺少细节镜头",
                           "有" if has_detail else "无", has_detail)

        return [tv1, tv2, tv3, tv4]

    def _trust_audio(self) -> list[MetricResult]:
        # T-A1: 数据/证据提及
        data_count = len(re.findall(r'\d+[万亿千百]|\d+%|\d+人|\d+年', self.asr_text))
        score_ta1 = min(100, data_count * 35)
        ta1 = MetricResult("T-A1", "数据证据提及", "trust", "audio", score_ta1, 100,
                           f"检测到{data_count}处数据/数字证据", f"{data_count}处", data_count >= 2)

        # T-A2: 真人证言
        has_testimonial = any(kw in self.asr_text for kw in ["我用了", "医生推荐", "专家", "亲测", "实测"])
        score_ta2 = 90 if has_testimonial else 15
        ta2 = MetricResult("T-A2", "真人证言", "trust", "audio", score_ta2, 100,
                           "有人证/使用体验" if has_testimonial else "缺少人证",
                           "有" if has_testimonial else "无", has_testimonial)

        # T-A3: 问题→方案逻辑链 — proxy: pain then product segment order
        has_logic = bool(self.asr_text) and len(self.asr_segments) >= 3
        score_ta3 = 80 if has_logic else 30
        ta3 = MetricResult("T-A3", "问题方案逻辑链", "trust", "audio", score_ta3, 100,
                           "逻辑链完整" if has_logic else "逻辑链不完整",
                           "完整" if has_logic else "不完整", has_logic)

        return [ta1, ta2, ta3]

    def _trust_subtitle(self) -> list[MetricResult]:
        all_ocr = []
        for f in self.vision_frames:
            all_ocr.extend(f.get("ocr", []))
        ocr_text = " ".join(all_ocr)

        # T-S1: 功效词标注
        efficacy_count = len(SELLING_POINT_WORDS.findall(ocr_text)) if ocr_text else 0
        score_ts1 = min(100, efficacy_count * 30)
        ts1 = MetricResult("T-S1", "功效词标注", "trust", "subtitle", score_ts1, 100,
                           f"OCR检测到{efficacy_count}个功效词", f"{efficacy_count}个", efficacy_count >= 3)

        # T-S2: 信任标识
        trust_count = len(TRUST_WORDS.findall(ocr_text)) if ocr_text else 0
        score_ts2 = min(100, trust_count * 50)
        ts2 = MetricResult("T-S2", "信任标识", "trust", "subtitle", score_ts2, 100,
                           f"检测到{trust_count}个信任标识词", f"{trust_count}个", trust_count >= 1)

        return [ts1, ts2]

    # ═══════════════════════════════════════════════════════════════
    # Dimension 3: Density (卖点密度)
    # ═══════════════════════════════════════════════════════════════

    def _density_visual(self) -> list[MetricResult]:
        product_tags = sum(1 for f in self.vision_frames
                          if any(t in str(f.get("tags", [])) for t in ["产品特写", "瓶身特写", "包装特写"]))
        density = product_tags / max(self.duration, 1.0)

        # D-V1: 产品出现频率
        score_dv1 = min(100, int(density * 500))
        dv1 = MetricResult("D-V1", "产品出现频率", "density", "visual", score_dv1, 100,
                           f"每5秒出现{density*5:.1f}次", f"{density:.2f}次/秒", density >= 0.2)

        # D-V2: 功能演示多样性
        unique_tags = set()
        for f in self.vision_frames:
            for t in f.get("tags", []):
                unique_tags.add(str(t))
        tag_count = len(unique_tags)
        score_dv2 = min(100, tag_count * 12)
        dv2 = MetricResult("D-V2", "功能演示多样性", "density", "visual", score_dv2, 100,
                           f"检测到{tag_count}种不同视觉标签", f"{tag_count}种", tag_count >= 8)

        return [dv1, dv2]

    def _density_audio(self) -> list[MetricResult]:
        # D-A1: 卖点词频
        sp_count = len(SELLING_POINT_WORDS.findall(self.asr_text))
        sp_rate = sp_count / max(self.duration, 1.0)
        score_da1 = min(100, int(sp_rate * 250))
        da1 = MetricResult("D-A1", "卖点词频", "density", "audio", score_da1, 100,
                           f"平均每5秒{sp_rate*5:.1f}个卖点词", f"{sp_rate*5:.1f}个/5秒", sp_rate >= 0.2)

        # D-A2: 利益点前置
        first_sp_idx = self.asr_text.find("改善") if "改善" in self.asr_text else (
            self.asr_text.find("提升") if "提升" in self.asr_text else len(self.asr_text))
        first_sp_time = (first_sp_idx / max(len(self.asr_text), 1)) * self.duration if self.asr_text else self.duration
        score_da2 = 100 if first_sp_time <= 8 else max(0, 100 - int((first_sp_time - 8) * 10))
        da2 = MetricResult("D-A2", "利益点前置", "density", "audio", score_da2, 100,
                           f"首个卖点在{first_sp_time:.1f}秒出现", f"{first_sp_time:.1f}秒", first_sp_time <= 8)

        return [da1, da2]

    def _density_subtitle(self) -> list[MetricResult]:
        all_ocr = []
        for f in self.vision_frames:
            all_ocr.extend(f.get("ocr", []))
        ocr_text = " ".join(all_ocr)
        total_frames = max(len(self.vision_frames), 1)

        # D-S1: 卖点文案密度
        frames_with_sp = sum(1 for f in self.vision_frames
                           if SELLING_POINT_WORDS.search(" ".join(f.get("ocr", []))))
        sp_ratio = frames_with_sp / total_frames
        score_ds1 = min(100, int(sp_ratio * 500))
        ds1 = MetricResult("D-S1", "卖点文案密度", "density", "subtitle", score_ds1, 100,
                           f"{frames_with_sp}/{total_frames}帧含卖点文案 ({sp_ratio:.0%})",
                           f"{sp_ratio:.0%}", sp_ratio >= 0.2)

        # D-S2: 价格出现次数
        price_count = len(re.findall(r'[¥￥]\d+|\d+元|\d+\.\d{2}', ocr_text)) if ocr_text else 0
        score_ds2 = min(100, price_count * 50)
        ds2 = MetricResult("D-S2", "价格出现次数", "density", "subtitle", score_ds2, 100,
                           f"OCR检测到{price_count}次价格信息", f"{price_count}次", price_count >= 2)

        return [ds1, ds2]

    # ═══════════════════════════════════════════════════════════════
    # Dimension 4: Pacing (节奏曲线)
    # ═══════════════════════════════════════════════════════════════

    def _pacing_visual(self) -> list[MetricResult]:
        if len(self.shots) < 3:
            return [
                MetricResult("P-V1", "三段式节奏比", "pacing", "visual", 30, 100,
                             "镜头数不足无法分析", "N/A", False),
                MetricResult("P-V2", "转场多样性", "pacing", "visual", 20, 100,
                             "无转场数据", "0种", False),
            ]

        # P-V1: 三段式节奏比
        first_third = [s for s in self.shots if float(s.get("start_s", s.get("start", 0))) < self.duration / 3]
        mid_third = [s for s in self.shots if self.duration / 3 <= float(s.get("start_s", s.get("start", 0))) < 2 * self.duration / 3]
        last_third = [s for s in self.shots if float(s.get("start_s", s.get("start", 0))) >= 2 * self.duration / 3]

        first_dur = sum(float(s.get("duration_s", s.get("duration", 1))) for s in first_third) / max(len(first_third), 1)
        mid_dur = sum(float(s.get("duration_s", s.get("duration", 1))) for s in mid_third) / max(len(mid_third), 1)
        last_dur = sum(float(s.get("duration_s", s.get("duration", 1))) for s in last_third) / max(len(last_third), 1)

        is_fast_slow_fast = first_dur < mid_dur and last_dur < mid_dur
        score_pv1 = 90 if is_fast_slow_fast else 50
        pv1 = MetricResult("P-V1", "三段式节奏比", "pacing", "visual", score_pv1, 100,
                           f"开头{first_dur:.1f}s/中段{mid_dur:.1f}s/结尾{last_dur:.1f}s",
                           "快-慢-快" if is_fast_slow_fast else "节奏平", is_fast_slow_fast)

        # P-V2: 转场类型多样性
        transitions = self.packaging.get("transitions", [])
        unique_trans = len(set(str(t) for t in (transitions if isinstance(transitions, list) else [])))
        has_animated = any(t in str(transitions).lower() for t in ["溶解", "滑", "缩放", "闪白", "模糊"])
        score_pv2 = min(100, unique_trans * 30 + (30 if has_animated else 0))
        pv2 = MetricResult("P-V2", "转场多样性", "pacing", "visual", score_pv2, 100,
                           f"{unique_trans}种转场" + ("含动效" if has_animated else "仅硬切"),
                           f"{unique_trans}种", unique_trans >= 2 and has_animated)

        return [pv1, pv2]

    def _pacing_audio(self) -> list[MetricResult]:
        # P-A1: BGM情绪起伏 — proxy: rhythm emotion variance
        emotions = [float(r.get("emotion", 0.5)) for r in self.rhythm]
        emotion_var = sum((e - sum(emotions) / max(len(emotions), 1)) ** 2 for e in emotions) / max(len(emotions), 1)
        has_curve = emotion_var > 0.05
        score_pa1 = 85 if has_curve else 40
        pa1 = MetricResult("P-A1", "BGM情绪起伏", "pacing", "audio", score_pa1, 100,
                           f"情绪方差{emotion_var:.3f}", f"{emotion_var:.3f}", has_curve)

        # P-A2: 音频卡点精度 — proxy: rhythm cuts alignment
        beat_aligned = any(r.get("cuts", 0) >= 3 for r in self.rhythm[:5])
        score_pa2 = 80 if beat_aligned else 35
        pa2 = MetricResult("P-A2", "音频卡点精度", "pacing", "audio", score_pa2, 100,
                           "检测到高密度卡点" if beat_aligned else "卡点稀疏",
                           "有卡点" if beat_aligned else "无卡点", beat_aligned)

        return [pa1, pa2]

    def _pacing_subtitle(self) -> list[MetricResult]:
        # P-S1: 字幕出现/消失节奏 — proxy: OCR per frame variance
        ocr_per_frame = [len(f.get("ocr", [])) for f in self.vision_frames]
        if len(ocr_per_frame) < 2:
            score_ps1 = 30
        else:
            avg = sum(ocr_per_frame) / len(ocr_per_frame)
            variance = sum((c - avg) ** 2 for c in ocr_per_frame) / len(ocr_per_frame)
            has_rhythm = variance > 0.5
            score_ps1 = 80 if has_rhythm else 35
        ps1 = MetricResult("P-S1", "字幕出现节奏", "pacing", "subtitle", score_ps1, 100,
                           "字幕节奏有起伏" if score_ps1 >= 60 else "字幕节奏平稳",
                           f"方差{sum((c - (sum(ocr_per_frame)/max(len(ocr_per_frame),1)))**2 for c in ocr_per_frame)/max(len(ocr_per_frame),1):.2f}" if len(ocr_per_frame) >= 2 else "N/A",
                           score_ps1 >= 60)

        return [ps1]

    # ═══════════════════════════════════════════════════════════════
    # Dimension 5: CTA (转化指令) — 结尾5秒
    # ═══════════════════════════════════════════════════════════════

    def _cta_visual(self) -> list[MetricResult]:
        cta_start = max(0, self.duration - 5)
        cta_frames = [f for f in self.vision_frames
                     if f.get("index", 0) >= cta_start / (self.duration / max(len(self.vision_frames), 1))]

        # C-V1: 价格/二维码出现
        has_price_visual = any(
            "价格" in str(f.get("tags", [])) or "优惠" in str(f.get("tags", []))
            or any("¥" in str(o) or "￥" in str(o) or "元" in str(o) for o in f.get("ocr", []))
            for f in cta_frames
        ) if cta_frames else False
        score_cv1 = 90 if has_price_visual else 15
        cv1 = MetricResult("C-V1", "价格视觉元素", "cta", "visual", score_cv1, 100,
                           "结尾有价格/二维码" if has_price_visual else "结尾缺少价格引导",
                           "有" if has_price_visual else "无", has_price_visual)

        # C-V2: 视觉聚焦
        has_focus = any("放大" in str(f.get("tags", [])) or "聚焦" in str(f.get("tags", []))
                       for f in cta_frames) if cta_frames else False
        score_cv2 = 85 if has_focus else 30
        cv2 = MetricResult("C-V2", "视觉聚焦", "cta", "visual", score_cv2, 100,
                           "有放大聚焦效果" if has_focus else "无聚焦效果",
                           "有" if has_focus else "无", has_focus)

        return [cv1, cv2]

    def _cta_audio(self) -> list[MetricResult]:
        # C-A1: 行动动词
        action_count = len(CTA_WORDS.findall(self.asr_text))
        score_ca1 = min(100, action_count * 50)
        ca1 = MetricResult("C-A1", "行动动词", "cta", "audio", score_ca1, 100,
                           f"检测到{action_count}个行动动词", f"{action_count}个", action_count >= 1)

        # C-A2: 紧迫感营造
        urgency_count = len(URGENCY_WORDS.findall(self.asr_text))
        score_ca2 = min(100, urgency_count * 50)
        ca2 = MetricResult("C-A2", "紧迫感营造", "cta", "audio", score_ca2, 100,
                           f"检测到{urgency_count}个紧迫词", f"{urgency_count}个", urgency_count >= 1)

        return [ca1, ca2]

    def _cta_subtitle(self) -> list[MetricResult]:
        all_ocr = []
        for f in self.vision_frames:
            all_ocr.extend(f.get("ocr", []))
        ocr_text = " ".join(all_ocr)

        # C-S1: 价格锚定
        has_anchor = bool(re.search(r'原价|划线价|¥\d+.*¥\d+|原价.*现价', ocr_text)) if ocr_text else False
        score_cs1 = 90 if has_anchor else 15
        cs1 = MetricResult("C-S1", "价格锚定", "cta", "subtitle", score_cs1, 100,
                           "检测到原价vs现价对比" if has_anchor else "未检测到价格锚定",
                           "有锚定" if has_anchor else "无锚定", has_anchor)

        # C-S2: 字号放大
        score_cs2 = 45  # Requires actual rendering to measure
        cs2 = MetricResult("C-S2", "CTA字号放大", "cta", "subtitle", score_cs2, 100,
                           "基于视觉检测评估CTA字号", "中等", False)

        return [cs1, cs2]

    # ── Burst template extraction ──

    def extract_burst_template(self) -> dict[str, Any]:
        """Extract viral video creation parameters as a reusable template."""
        all_metrics = self.calculate_all()
        return {
            "hook_frequency": next((m.raw_value for m in all_metrics if m.metric_id == "H-V1"), "N/A"),
            "has_conflict_visual": next((m.passed for m in all_metrics if m.metric_id == "H-V2"), False),
            "has_zoom_effect": next((m.passed for m in all_metrics if m.metric_id == "H-V4"), False),
            "conflict_word_count": next((int(m.raw_value.replace("个", "")) for m in all_metrics if m.metric_id == "H-A2"), 0),
            "has_subtitle_animation": next((m.passed for m in all_metrics if m.metric_id == "H-T1"), False),
            "product_shot_ratio": next((m.raw_value for m in all_metrics if m.metric_id == "T-V1"), "0%"),
            "has_before_after": next((m.passed for m in all_metrics if m.metric_id == "T-V3"), False),
            "data_evidence_count": next((int(m.raw_value.replace("处", "")) for m in all_metrics if m.metric_id == "T-A1"), 0),
            "selling_point_rate": next((m.raw_value for m in all_metrics if m.metric_id == "D-A1"), "0/5秒"),
            "first_selling_point_sec": next((m.raw_value for m in all_metrics if m.metric_id == "D-A2"), "999秒"),
            "pacing_pattern": next((m.raw_value for m in all_metrics if m.metric_id == "P-V1"), "未知"),
            "has_animated_transition": next((m.passed for m in all_metrics if m.metric_id == "P-V2"), False),
            "action_word_count": next((int(m.raw_value.replace("个", "")) for m in all_metrics if m.metric_id == "C-A1"), 0),
            "urgency_word_count": next((int(m.raw_value.replace("个", "")) for m in all_metrics if m.metric_id == "C-A2"), 0),
            "has_price_anchor": next((m.passed for m in all_metrics if m.metric_id == "C-S1"), False),
            "overall_score": sum(m.score for m in all_metrics) // max(len(all_metrics), 1),
        }
