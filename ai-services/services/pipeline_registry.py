"""Pipeline Registry — Pixelle-Video inspired plugin system.

Allows registering different rendering/analysis pipelines that can be
discovered and selected at runtime. Foundation for future multi-pipeline
expansion (Standard, Quick, Premium, etc.).

Usage:
    from services.pipeline_registry import registry, PipelineSpec

    @registry.register
    class StandardPipeline(PipelineSpec):
        name = "standard"
        display_name = "Standard Structure Migration"
        description = "Full analysis → structure extraction → migration → rendering"

    # List all available pipelines
    for spec in registry.list():
        print(spec.name, spec.display_name)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class PipelineSpec:
    """Metadata for a registered pipeline."""
    name: str
    display_name: str = ""
    description: str = ""
    icon: str = "🎬"
    enabled: bool = True
    # Optional factory to create the pipeline instance
    factory: Optional[Callable[[], Any]] = None
    # Metadata
    tags: list[str] = field(default_factory=list)
    requires_comfyui: bool = False
    requires_tts: bool = True


class PipelineRegistry:
    """Registry of available rendering pipelines.

    Pipelines register themselves via the @register decorator.
    The frontend can query /api/v1/pipelines to discover available pipelines.
    """

    def __init__(self) -> None:
        self._pipelines: dict[str, PipelineSpec] = {}

    def register(self, spec_or_cls: PipelineSpec | type) -> PipelineSpec:
        """Register a pipeline. Can be used as decorator or direct call."""
        if isinstance(spec_or_cls, PipelineSpec):
            spec = spec_or_cls
        else:
            # Class-based registration
            cls = spec_or_cls
            spec = PipelineSpec(
                name=getattr(cls, 'name', cls.__name__.lower()),
                display_name=getattr(cls, 'display_name', cls.__name__),
                description=getattr(cls, 'description', ''),
                icon=getattr(cls, 'icon', '🎬'),
                tags=getattr(cls, 'tags', []),
            )
        self._pipelines[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[PipelineSpec]:
        """Get a pipeline by name."""
        return self._pipelines.get(name)

    def list(self, enabled_only: bool = True) -> list[PipelineSpec]:
        """List all registered pipelines."""
        specs = list(self._pipelines.values())
        if enabled_only:
            specs = [s for s in specs if s.enabled]
        return specs

    def list_names(self) -> list[str]:
        """List registered pipeline names."""
        return list(self._pipelines.keys())


# ── Global registry instance ──
registry = PipelineRegistry()


# ── Register built-in pipelines ──

@registry.register
class StandardPipeline:
    """Default pipeline: full structure analysis → migration → rendering."""
    name = "standard"
    display_name = "Standard"
    icon = "🔬"
    description = "Full structure analysis, LLM migration, AI visual generation, and video rendering"
    tags = ["structure", "migration", "rendering"]
    requires_comfyui = False
    requires_tts = True


@registry.register
class QuickPipeline:
    """Fast pipeline: minimal analysis, direct rendering with AI visuals."""
    name = "quick"
    display_name = "Quick Create"
    icon = "⚡"
    description = "Fast text-to-video generation with AI visuals — minimal analysis"
    tags = ["quick", "ai-generation"]
    requires_comfyui = True
    requires_tts = True


@registry.register
class PremiumPipeline:
    """Premium pipeline: ComfyUI video generation for key segments."""
    name = "premium"
    display_name = "Premium AI Video"
    icon = "✨"
    description = "Full pipeline with ComfyUI WAN 2.2 video generation for Hook and Product segments"
    tags = ["premium", "ai-video", "comfyui"]
    requires_comfyui = True
    requires_tts = True
