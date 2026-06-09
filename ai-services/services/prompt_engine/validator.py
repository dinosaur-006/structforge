"""PromptQualityValidator — scores prompts before output.

7 checks, 100 points max. Below 70 → reject and regenerate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityReport:
    score: int
    passed: bool
    feedback: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PromptQualityValidator:
    MIN_SCORE = 70

    CHECKS: list[tuple[str, int, str]] = [
        ("length", 15, "Prompt length within acceptable range"),
        ("subject_position", 20, "First 30 words contain clear subject description"),
        ("camera_present", 20, "Contains shot size or camera movement terminology"),
        ("style_present", 15, "Contains lighting description or color tone"),
        ("no_ambiguity", 10, "No vague adjectives (pretty/nice/good/great)"),
        ("negative_balance", 10, "3-5 negative prompts, not too few or too many"),
        ("platform_valid", 10, "Matches target platform syntax conventions"),
    ]

    # Vague words that indicate poor prompt quality
    VAGUE_WORDS_EN = {"pretty", "nice", "good", "great", "beautiful", "amazing", "awesome", "cool", "lovely"}
    VAGUE_WORDS_CN = {"漂亮", "高级", "很好的", "非常好看", "很不错", "挺好的", "还行"}

    # Camera terminology that must appear at least once
    CAMERA_TERMS_SEEDANCE = {"推", "拉", "移", "跟", "静", "摇", "环绕", "dolly", "push", "pull", "pan", "track", "gimbal", "tripod", "handheld", "zoom", "close-up", "wide", "medium shot"}
    CAMERA_TERMS_RUNWAY = {"dolly", "pan", "tilt", "track", "gimbal", "tripod", "handheld", "zoom", "push", "pull", "orbit", "close-up", "wide shot", "medium shot", "locked-off"}
    CAMERA_TERMS_KLING = {"镜头", "推", "拉", "移", "跟", "摇", "环绕", "固定", "手持", "特写", "中景", "远景"}

    # Platform syntax markers
    PLATFORM_MARKERS = {
        "seedance": ["9:16", "构图", "--ar", "--style"],
        "runway": [],  # no specific markers required
        "kling": [],   # no specific markers required
    }

    def validate(self, prompt_text: str, *, platform: str = "seedance", segment_type: str = "product") -> QualityReport:
        """Score a prompt and return quality report."""
        feedback: list[str] = []
        warnings: list[str] = []
        total_score = 0

        # 1. Length check (15 pts)
        length_score = self._check_length(prompt_text, platform)
        total_score += length_score
        if length_score < 10:
            feedback.append(f"Length score {length_score}/15: prompt may be too short or too long for {platform}")

        # 2. Subject position (20 pts)
        subject_score = self._check_subject(prompt_text, platform)
        total_score += subject_score
        if subject_score < 15:
            feedback.append(f"Subject score {subject_score}/20: first 30 chars should describe the product")

        # 3. Camera present (20 pts)
        camera_score = self._check_camera(prompt_text, platform)
        total_score += camera_score
        if camera_score < 15:
            feedback.append(f"Camera score {camera_score}/20: add shot size or camera movement terminology")

        # 4. Style present (15 pts)
        style_score = self._check_style(prompt_text)
        total_score += style_score
        if style_score < 10:
            feedback.append(f"Style score {style_score}/15: add lighting or color tone description")

        # 5. No ambiguity (10 pts)
        ambiguity_score = self._check_ambiguity(prompt_text, platform)
        total_score += ambiguity_score
        if ambiguity_score < 10:
            feedback.append(f"Ambiguity: remove vague adjectives like '漂亮', 'nice', 'good'")

        # 6. Negative balance (10 pts)
        negative_count = prompt_text.lower().count("no ")
        if 3 <= negative_count <= 6:
            total_score += 10
        elif negative_count < 3:
            total_score += 5
            warnings.append(f"Only {negative_count} negative terms — consider adding 1-2 more for quality")
        else:
            total_score += 7
            warnings.append(f"Too many negative terms ({negative_count}) — may blur output, keep 3-5")

        # 7. Platform syntax (10 pts)
        platform_score = self._check_platform(prompt_text, platform)
        total_score += platform_score
        if platform_score < 8:
            feedback.append(f"Platform score {platform_score}/10: missing {platform}-specific syntax markers")

        passed = total_score >= self.MIN_SCORE
        return QualityReport(score=total_score, passed=passed, feedback=feedback, warnings=warnings)

    # ── Private check methods ──

    def _check_length(self, prompt: str, platform: str) -> int:
        words = prompt.split()
        wc = len(words)
        if platform == "runway":
            if 10 <= wc <= 40:
                return 15
            elif 5 <= wc <= 60:
                return 10
            return 5
        else:  # seedance / kling
            if 20 <= wc <= 120:
                return 15
            elif 10 <= wc <= 160:
                return 10
            return 5

    def _check_subject(self, prompt: str, platform: str) -> int:
        first_80 = prompt[:80] if platform in ("seedance", "kling") else prompt[:50]
        subject_hints = ["产品", "特写", "展示", "广告", "product", "close-up", "shot of", "showcasing",
                         "构图", "电商", "食品", "美妆", "电子", "服饰", "家居", "饮料", "零食"]
        count = sum(1 for h in subject_hints if h.lower() in first_80.lower())
        return min(20, count * 5)

    def _check_camera(self, prompt: str, platform: str) -> int:
        terms = {
            "seedance": self.CAMERA_TERMS_SEEDANCE,
            "runway": self.CAMERA_TERMS_RUNWAY,
            "kling": self.CAMERA_TERMS_KLING,
        }.get(platform, self.CAMERA_TERMS_SEEDANCE)
        count = sum(1 for t in terms if t.lower() in prompt.lower())
        return min(20, count * 5)

    def _check_style(self, prompt: str) -> int:
        style_hints = ["light", "lighting", "studio", "natural", "soft", "warm", "cool",
                        "tone", "color", "grade", "shadow", "bright", "dark", "contrast",
                        "光", "灯", "色", "影", "暖", "冷"]
        count = sum(1 for h in style_hints if h.lower() in prompt.lower())
        return min(15, count * 4)

    def _check_ambiguity(self, prompt: str, platform: str) -> int:
        text = prompt.lower()
        en_hits = sum(1 for w in self.VAGUE_WORDS_EN if f" {w} " in f" {text} " or text.startswith(f"{w} "))
        cn_hits = sum(1 for w in self.VAGUE_WORDS_CN if w in prompt)
        return max(0, 10 - (en_hits + cn_hits) * 5)

    def _check_platform(self, prompt: str, platform: str) -> int:
        markers = self.PLATFORM_MARKERS.get(platform, [])
        if not markers:
            return 10
        count = sum(1 for m in markers if m.lower() in prompt.lower())
        return min(10, count * 4)
