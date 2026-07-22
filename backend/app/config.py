from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOMOS_AUDIT_", env_file=".env", extra="ignore"
    )

    model: str = "claude-opus-4-8"
    # Effort per pipeline stage — classification is routine, the audit is
    # intelligence-sensitive.
    classification_effort: str = "medium"
    audit_effort: str = "high"
    max_output_tokens: int = 16000
    # Hard input guard (characters). Well below the 1M-token context window,
    # generous enough for any realistic Greek δικόγραφο.
    max_document_chars: int = 400_000
    min_document_chars: int = 200

    # Optional bearer token. Empty string disables auth (localhost use).
    api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
