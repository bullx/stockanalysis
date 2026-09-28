import asyncio
from typing import Any

import httpx

from backend.app.config.providers import PROVIDERS
from backend.app.settings import Settings, get_settings
from backend.app.utils.mock_llm import mock_completion


class LlmStopped(Exception):
    """The desk asked to stop, or the model connection failed. Do not start another call."""


class LlmGate:
    """Owns the in-flight HTTP client so a stop closes the socket and aborts generation."""

    def __init__(self) -> None:
        self.stop_requested = False
        self.clients: set[httpx.AsyncClient] = set()

    def raise_if_stopped(self) -> None:
        if self.stop_requested:
            raise LlmStopped("Stopped. The model request was cancelled.")

    async def request_stop(self) -> None:
        self.stop_requested = True
        for client in list(self.clients):
            if not client.is_closed:
                await client.aclose()


def _fatal_llm_error(error: Exception) -> bool:
    if isinstance(error, (LlmStopped, ConnectionError, TimeoutError)):
        return True
    message = str(error)
    return message.startswith("LLM API 5")


async def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 800,
    options: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    options = options or {}
    provider_name = (options.get("provider") or settings.llm_provider).lower()
    api_key = options.get("api_key") or settings.llm_api_key
    model_name = options.get("model") or settings.llm_model
    provider = PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_name}")

    if provider_name == "mock":
        await asyncio.sleep(0.12)
        return mock_completion(system_prompt, user_message)

    supports_system = provider.get("supports_system", True)
    if supports_system and system_prompt:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    else:
        messages = [
            {
                "role": "user",
                "content": f"[INSTRUCTIONS]\n{system_prompt}\n\n[TASK]\n{user_message}",
            }
        ]

    body_opts = {
        **options,
        "context_window": options.get("context_window") or settings.local_context_window,
    }
    body = provider["body_mapper"](messages, max_tokens, model_name, body_opts)
    url = provider["endpoint"] + provider.get("query_param", lambda k: "")(api_key)
    headers = {"Content-Type": "application/json", **provider["auth_header"](api_key)}

    is_local = options.get("is_local")
    if is_local is None:
        is_local = settings.is_local
    timeout_ms = settings.local_llm_timeout_ms if is_local else 60_000
    timeout = httpx.Timeout(timeout_ms / 1000, connect=15.0)
    gate: LlmGate | None = options.get("gate")
    if gate:
        gate.raise_if_stopped()

    async with httpx.AsyncClient(timeout=timeout) as client:
        if gate:
            gate.clients.add(client)
        try:
            if gate:
                gate.raise_if_stopped()
            response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"LLM call timed out after {timeout_ms / 1000:.0f}s — model may be too slow"
            ) from exc
        except httpx.HTTPError as exc:
            if gate and gate.stop_requested:
                raise LlmStopped("Stopped. The model request was cancelled.") from exc
            raise ConnectionError(f"LLM connection failed: {exc}") from exc
        finally:
            if gate:
                gate.clients.discard(client)

    if response.status_code >= 400:
        raise RuntimeError(f"LLM API {response.status_code}: {response.text[:500]}")

    data = response.json()
    return provider["response_extractor"](data)


async def call_llm_with_retry(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    max_retries: int = 2,
    **kwargs,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            text = (await call_llm(system_prompt, user_message, max_tokens, **kwargs) or "").strip()
            if text:
                return text
            last_error = RuntimeError("LLM returned empty response")
        except Exception as error:  # noqa: BLE001
            last_error = error
        if _fatal_llm_error(last_error):
            raise last_error
        msg = str(last_error).lower()
        delay = 5 * attempt if ("429" in msg or "rate limit" in msg) else 1 * attempt
        if attempt == max_retries:
            break
        await asyncio.sleep(delay)
    assert last_error
    raise last_error
