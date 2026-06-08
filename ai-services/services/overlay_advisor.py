"""Recommend overlay/sticker elements based on segment script content."""

from __future__ import annotations

from typing import Any

# Keyword → overlay recommendation mapping.
OVERLAY_RULES: list[dict[str, Any]] = [
    {
        "keywords": ["价格", "元", "售价", "优惠", "折扣", "price", "offer"],
        "overlay": "价格角标",
        "style": "drawtext=text='PRICE':fontcolor=white:fontsize=48:box=1:boxcolor=#C85555@0.85:boxborderw=8:x=80:y=1600",
        "description": "在画面左下角添加价格提示角标",
    },
    {
        "keywords": ["限时", "限量", "倒计时", "最后", "抢购", "limited", "最后机会"],
        "overlay": "紧迫感标签",
        "style": "drawtext=text='LIMITED':fontcolor=#FFFFFF:fontsize=52:box=1:boxcolor=#C87D53@0.9:boxborderw=10:x=80:y=400",
        "description": "在画面上方添加限时标签",
    },
    {
        "keywords": ["新品", "首发", "全新", "新款", "new", "launch"],
        "overlay": "新品标签",
        "style": "drawtext=text='NEW':fontcolor=white:fontsize=48:box=1:boxcolor=#5C8B67@0.85:boxborderw=8:x=80:y=400",
        "description": "添加新品标签",
    },
    {
        "keywords": ["对比", "vs", "比较", "之前", "之后", "before", "after", "compare"],
        "overlay": "对比分屏线",
        "style": "drawbox=x=iw/2-2:y=0:w=4:h=ih:color=white@0.6:t=fill",
        "description": "在画面中央添加对比分屏线",
    },
    {
        "keywords": ["数据", "测试", "认证", "实测", "实验", "data", "certified"],
        "overlay": "数据标签",
        "style": "drawtext=text='VERIFIED':fontcolor=#5C8B67:fontsize=44:box=1:boxcolor=white@0.85:boxborderw=6:x=80:y=1600",
        "description": "左下角添加数据认证标签",
    },
    {
        "keywords": ["前", "名", "送", "赠", "free", "赠送", "礼包"],
        "overlay": "赠品标签",
        "style": "drawtext=text='GIFT':fontcolor=white:fontsize=48:box=1:boxcolor=#D4A24E@0.9:boxborderw=8:x=80:y=1600",
        "description": "添加赠品提示标签",
    },
]


class OverlayAdvisor:
    """Recommend overlay elements for segments based on script content."""

    def recommend(self, script_text: str) -> list[dict[str, Any]]:
        """Return overlay recommendations for a single segment's script text."""
        lower = script_text.lower()
        results: list[dict[str, Any]] = []
        for rule in OVERLAY_RULES:
            if any(kw.lower() in lower for kw in rule["keywords"]):
                results.append({
                    "overlay": rule["overlay"],
                    "style": rule["style"],
                    "description": rule["description"],
                })
        # Deduplicate by overlay name.
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for r in results:
            if r["overlay"] not in seen:
                seen.add(r["overlay"])
                deduped.append(r)
        return deduped[:3]  # Max 3 overlays per segment.

    def recommend_for_script(self, segments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Return overlay recommendations for every segment in a script."""
        recs: dict[str, list[dict[str, Any]]] = {}
        for seg in segments:
            text = str(seg.get("script", "") or seg.get("copy", ""))
            if text:
                result = self.recommend(text)
                if result:
                    recs[str(seg["id"])] = result
        return recs
