import re
from typing import Any, Callable

BodyMapper = Callable[..., dict[str, Any]]
AuthHeader = Callable[[str], dict[str, str]]
Extractor = Callable[[dict[str, Any]], str]


def _openai_compat_body(messages, max_tokens, model, options=None, default_model="gpt-4o"):
    options = options or {}
    return {
        "model": model or default_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": options.get("temperature", 0.3),
        "stream": False,
    }


def _strip_think(text: str) -> str:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.I)
    return cleaned.strip()


def _openai_extract(data: dict[str, Any]) -> str:
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    return _strip_think(content) or _strip_think(str(reasoning))


def _ollama_extract(data: dict[str, Any]) -> str:
    msg = data.get("message") or {}
    content = _strip_think(msg.get("content") or "")
    if content:
        return content
    return (msg.get("thinking") or "").strip()


def _ollama_body(messages, max_tokens, model, options=None):
    options = options or {}
    return {
        "model": model or "llama3.1:8b",
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": options.get("temperature", 0.3),
            "num_ctx": options.get("context_window", 8192),
        },
    }


PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": f"Bearer {key}"},
        "supports_system": True,
        "default_model": "gpt-4o",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(m, t, model, o, "gpt-4o"),
        "response_extractor": _openai_extract,
    },
    "anthropic": {
        "endpoint": "https://api.anthropic.com/v1/messages",
        "auth_header": lambda key: {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        "supports_system": True,
        "default_model": "claude-3-5-sonnet-20241022",
        "body_mapper": lambda messages, max_tokens, model, options=None: {
            "model": model or "claude-3-5-sonnet-20241022",
            "max_tokens": max_tokens,
            "system": next((x["content"] for x in messages if x["role"] == "system"), ""),
            "messages": [x for x in messages if x["role"] != "system"],
        },
        "response_extractor": lambda data: data["content"][0]["text"],
    },
    "gemini": {
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
        "auth_header": lambda key: {},
        "query_param": lambda key: f"?key={key}",
        "supports_system": True,
        "default_model": "gemini-1.5-pro",
        "body_mapper": lambda messages, max_tokens, model, options=None: {
            "contents": [
                {
                    "role": "user" if m["role"] == "user" else "model",
                    "parts": [{"text": m["content"]}],
                }
                for m in messages
                if m["role"] != "system"
            ],
            "systemInstruction": {
                "parts": [
                    {
                        "text": next(
                            (x["content"] for x in messages if x["role"] == "system"),
                            "",
                        )
                    }
                ]
            },
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": (options or {}).get("temperature", 0.3),
            },
        },
        "response_extractor": lambda data: data["candidates"][0]["content"]["parts"][0]["text"],
    },
    "mistral": {
        "endpoint": "https://api.mistral.ai/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": f"Bearer {key}"},
        "supports_system": True,
        "default_model": "mistral-large-latest",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(
            m, t, model, o, "mistral-large-latest"
        ),
        "response_extractor": _openai_extract,
    },
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": f"Bearer {key}"},
        "supports_system": True,
        "default_model": "llama-3.1-70b-versatile",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(
            m, t, model, o, "llama-3.1-70b-versatile"
        ),
        "response_extractor": _openai_extract,
    },
    "openrouter": {
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": f"Bearer {key}"},
        "supports_system": True,
        "default_model": "meta-llama/llama-3.1-70b-instruct",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(
            m, t, model, o, "meta-llama/llama-3.1-70b-instruct"
        ),
        "response_extractor": _openai_extract,
    },
    "ollama": {
        "endpoint": "http://localhost:11434/api/chat",
        "auth_header": lambda key: {},
        "supports_system": True,
        "default_model": "llama3.1:8b",
        "body_mapper": _ollama_body,
        "response_extractor": _ollama_extract,
    },
    "lmstudio": {
        "endpoint": "http://localhost:1234/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": "Bearer lm-studio"},
        "supports_system": True,
        "default_model": "local-model",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(
            m, t, model, o, "local-model"
        ),
        "response_extractor": _openai_extract,
    },
    "llamacpp": {
        "endpoint": "http://localhost:8080/v1/chat/completions",
        "auth_header": lambda key: {},
        "supports_system": True,
        "default_model": "local",
        "body_mapper": lambda messages, max_tokens, model, options=None: {
            "model": "local",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": (options or {}).get("temperature", 0.3),
            "stream": False,
            "cache_prompt": True,
        },
        "response_extractor": _openai_extract,
    },
    "jan": {
        "endpoint": "http://localhost:1337/v1/chat/completions",
        "auth_header": lambda key: {"Authorization": "Bearer jan-local"},
        "supports_system": True,
        "default_model": "local-model",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(
            m, t, model, o, "local-model"
        ),
        "response_extractor": _openai_extract,
    },
    "llamafile": {
        "endpoint": "http://localhost:8080/v1/chat/completions",
        "auth_header": lambda key: {},
        "supports_system": True,
        "default_model": "local",
        "body_mapper": lambda m, t, model, o=None: _openai_compat_body(m, t, model, o, "local"),
        "response_extractor": _openai_extract,
    },
    "mock": {
        "endpoint": "http://localhost/mock",
        "auth_header": lambda key: {},
        "supports_system": True,
        "default_model": "mock",
        "body_mapper": lambda m, t, model, o=None: {},
        "response_extractor": lambda data: data.get("content", ""),
    },
}
