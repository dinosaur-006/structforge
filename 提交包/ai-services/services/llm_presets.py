"""LLM provider presets for quick configuration.

Usage:
    from services.llm_presets import get_preset, list_presets
    preset = get_preset("qwen")
    # → {"name": "Qwen Max", "base_url": "...", "model": "qwen-max", ...}
"""

from __future__ import annotations

from typing import Any

# ── Verified LLM presets (all OpenAI-compatible API) ──

PRESETS: dict[str, dict[str, Any]] = {
    "doubao": {
        "name": "Doubao Seed (Default)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "ep-20260508213828-7ntjl",
        "description": "ByteDance Doubao LLM — default for StructForge",
        "requires_api_key": True,
        "api_key_url": "https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint",
    },
    "qwen": {
        "name": "Qwen Max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-max",
        "description": "Alibaba Qwen — strong Chinese language support",
        "requires_api_key": True,
        "api_key_url": "https://bailian.console.aliyun.com/",
    },
    "qwen_plus": {
        "name": "Qwen Plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
        "description": "Alibaba Qwen Plus — fast and cost-effective",
        "requires_api_key": True,
        "api_key_url": "https://bailian.console.aliyun.com/",
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "description": "OpenAI GPT-4o — best overall quality",
        "requires_api_key": True,
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    "openai_mini": {
        "name": "OpenAI GPT-4o-mini",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "description": "OpenAI GPT-4o-mini — fast and cheap",
        "requires_api_key": True,
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    "deepseek": {
        "name": "DeepSeek V3",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "description": "DeepSeek V3 — strong reasoning, low cost",
        "requires_api_key": True,
        "api_key_url": "https://platform.deepseek.com/api_keys",
    },
    "deepseek_r1": {
        "name": "DeepSeek R1",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-reasoner",
        "description": "DeepSeek R1 — reasoning model, excellent for structure analysis",
        "requires_api_key": True,
        "api_key_url": "https://platform.deepseek.com/api_keys",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1/chat/completions",
        "model": "qwen2.5:7b",
        "description": "Local Ollama — no API key needed, privacy-first",
        "requires_api_key": False,
        "default_api_key": "ollama",
    },
    "zhipu": {
        "name": "Zhipu GLM-4",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4",
        "description": "Zhipu AI GLM-4 — strong Chinese+reasoning",
        "requires_api_key": True,
        "api_key_url": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    "moonshot": {
        "name": "Moonshot Kimi",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "model": "moonshot-v1-8k",
        "description": "Moonshot Kimi — long context Chinese",
        "requires_api_key": True,
        "api_key_url": "https://platform.moonshot.cn/console/api-keys",
    },
}


def list_presets() -> list[dict[str, Any]]:
    """Return all available LLM presets."""
    return [
        {
            "key": key,
            "name": preset["name"],
            "model": preset["model"],
            "description": preset["description"],
            "requires_api_key": preset["requires_api_key"],
        }
        for key, preset in PRESETS.items()
    ]


def get_preset(key: str) -> dict[str, Any] | None:
    """Get a specific preset by key. Returns None if not found."""
    return PRESETS.get(key)


def find_preset_by_model(model: str) -> str | None:
    """Find preset key by model name. Returns None if not found."""
    for key, preset in PRESETS.items():
        if preset["model"] == model:
            return key
    return None


def get_preset_names() -> list[str]:
    """Return list of preset keys."""
    return list(PRESETS.keys())
