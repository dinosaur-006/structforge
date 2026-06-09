"""Platform-specific prompt adapters."""

from .seedance import SeedanceAdapter
from .runway import RunwayAdapter
from .kling import KlingAdapter

__all__ = ["SeedanceAdapter", "RunwayAdapter", "KlingAdapter"]
