MODEL_TIERS = {
    "tier1": {
        "models": [
            "llama3.1:70b",
            "llama3.1:405b",
            "llama3.3:70b",
            "qwen2.5:72b",
            "qwen2.5:32b",
            "mistral-large",
            "deepseek-r1:70b",
            "deepseek-v3",
            "gemma3:27b",
            "gemma4:27b",
            "phi4:14b",
            "qwen3.6:35b",
            "qwen3.6:27b",
            "qwen3.5:27b",
            "qwen3:27b",
            "command-r-plus",
            "gpt-4o",
            "claude-3-5",
            "gemini-1.5-pro",
        ],
        "parallelism": "sequential",
        "max_tokens_agent": 1400,
        "max_tokens_debate": 1600,
        "max_tokens_cio": 2000,
        "context_window": 32768,
        "json_mode": "prompt",
        "system_prompt_mode": "native",
        "rounds_enabled": [1, 2, 3],
        "agent_count": 4,
        "simplify_prompts": False,
        "flatten_json": False,
    },
    "tier2": {
        "models": [
            "llama3.1:8b",
            "llama3.2:11b",
            "mistral:7b",
            "mixtral:8x7b",
            "qwen2.5:14b",
            "qwen2.5:7b",
            "deepseek-r1:14b",
            "deepseek-r1:8b",
            "gemma3:12b",
            "gemma3:4b",
            "gemma4:12b",
            "gemma4:4b",
            "phi3.5:3.8b",
            "phi4-mini",
            "gemma2:9b",
            "command-r",
            "mock",
        ],
        "parallelism": "sequential",
        "max_tokens_agent": 1000,
        "max_tokens_debate": 1200,
        "max_tokens_cio": 1500,
        "context_window": 8192,
        "json_mode": "prompt+schema",
        "system_prompt_mode": "native",
        "rounds_enabled": [1, 2, 3],
        "agent_count": 4,
        "simplify_prompts": True,
        "flatten_json": False,
    },
    "tier3": {
        "models": [
            "llama3.2:3b",
            "llama3.2:1b",
            "phi3:mini",
            "phi3.5:mini",
            "gemma2:2b",
            "gemma3:1b",
            "qwen2.5:3b",
            "qwen2.5:1.5b",
            "tinyllama",
            "smollm2",
        ],
        "parallelism": "sequential",
        "max_tokens_agent": 400,
        "max_tokens_debate": 600,
        "max_tokens_cio": 800,
        "context_window": 4096,
        "json_mode": "key-value",
        "system_prompt_mode": "inject",
        "rounds_enabled": [1, 3],
        "agent_count": 4,
        "simplify_prompts": True,
        "flatten_json": True,
    },
}


def detect_tier(model_name: str) -> tuple[str, dict]:
    name = (model_name or "").lower().strip()
    best: tuple[str, dict] | None = None
    best_len = -1
    for tier, config in MODEL_TIERS.items():
        for m in config["models"]:
            ml = m.lower()
            if name == ml or ml in name or name.startswith(ml):
                if len(ml) > best_len:
                    best_len = len(ml)
                    best = (tier, config)
    if best:
        return best
    return "tier2", MODEL_TIERS["tier2"]
