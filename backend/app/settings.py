from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_PROVIDERS = {"ollama", "lmstudio", "llamacpp", "jan", "llamafile", "mock"}


def provider_is_local(provider: str, provider_type: str | None = None) -> bool:
    """Decide locality from an effective provider, not just global .env settings.

    A provider chosen on the form has no provider_type, so fall back to the
    known-local provider set. An explicit provider_type wins when present.
    """
    ptype = (provider_type or "").lower()
    if ptype == "local":
        return True
    if ptype == "cloud":
        return False
    return (provider or "").lower() in LOCAL_PROVIDERS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:8b"
    llm_provider_type: str = "local"
    llm_api_key: str = ""
    local_llm_timeout_ms: int = 300_000
    local_agent_delay_ms: int = 500
    local_context_window: int = 8192
    enable_web_search: bool = False
    cors_origins: str = "http://localhost:5173"
    output_dir: str = "output"
    # Sent to SEC when SEC_USER_AGENT is unset. A personal email is not required.
    sec_user_agent: str = "Aurelia Investments research@example.com"

    @property
    def is_local(self) -> bool:
        return provider_is_local(self.llm_provider, self.llm_provider_type)


@lru_cache
def get_settings() -> Settings:
    return Settings()
