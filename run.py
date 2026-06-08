"""StructForge Video Optimization Pipeline — CLI entry point.

Usage:
    python run.py --video sample.mp4 --product "降噪耳机Pro" --type 3C \
                  --selling_points "主动降噪" "40h续航" "蓝牙5.3" --output outputs/final.mp4
"""

from __future__ import annotations

import argparse
import logging

from config import Settings
from services.optimization_models import (
    PlatformType,
    ProductProfile,
    ProductType,
    SellingPointNature,
)
from services.optimization_pipeline import OptimizationPipeline

log = logging.getLogger(__name__)

TYPE_MAP = {
    "美妆": ProductType.BEAUTY, "3C": ProductType.ELECTRONICS,
    "食品": ProductType.FOOD, "服装": ProductType.CLOTHING, "其他": ProductType.OTHER,
}


def main():
    parser = argparse.ArgumentParser(description="StructForge Video Optimization Pipeline v3")
    parser.add_argument("--video", required=True, help="输入视频路径")
    parser.add_argument("--product", required=True, help="产品名称")
    parser.add_argument("--type", required=True, choices=list(TYPE_MAP), help="产品类型")
    parser.add_argument("--selling_points", nargs="+", required=True, help="核心卖点")
    parser.add_argument("--audience", default="通用", help="目标人群")
    parser.add_argument("--offer", default="", help="优惠信息")
    parser.add_argument("--tone", default="", help="语气")
    parser.add_argument("--output", default="outputs/final.mp4", help="输出路径")
    parser.add_argument("--bgm", default="", help="背景音乐路径")
    parser.add_argument("--lut", default=None, help="LUT预设(不指定=自动推荐)")
    parser.add_argument("--protect-colors", action="store_true", help="开启产品色保护")
    args = parser.parse_args()

    product = ProductProfile(
        name=args.product,
        product_type=TYPE_MAP[args.type],
        selling_points=args.selling_points,
        target_audience=args.audience,
        offer=args.offer,
        tone=args.tone,
        platform=PlatformType.DOUYIN,
    )

    settings = Settings()
    pipeline = OptimizationPipeline(settings)

    print(f"Analyzing: {args.video}")
    print(f"Product: {args.product} ({args.type})")
    print(f"Selling points: {', '.join(args.selling_points)}")

    plan = pipeline.run(
        video_path=args.video,
        product=product,
        bgm_path=args.bgm,
        lut_preset=args.lut,
        protect_colors=args.protect_colors,
    )

    print(f"\n✅ Optimization plan generated")
    print(f"📊 Structure: {' → '.join(s.type.value for s in plan.structure.segments)}")
    print(f"   Total: {plan.structure.total_duration:.1f}s, {len(plan.structure.segments)} segments")
    keep = sum(1 for d in plan.decisions if d.decision.value == "keep")
    edit = sum(1 for d in plan.decisions if d.decision.value == "re-edit")
    gen = sum(1 for d in plan.decisions if d.decision.value == "ai-generate")
    print(f"🎬 Sources: {keep} kept | {edit} re-edited | {gen} AI-generated")
    print(f"🎞️  Transitions: {len(plan.transitions)} total, {plan.special_transition_count} special")
    print(f"📝 Subtitles: {len(plan.subtitles)} events")
    print(f"Output: {plan.output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
