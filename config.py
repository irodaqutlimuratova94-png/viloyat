from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://vb:vb@db:5432/vb"
    redis_url: str = ""  # bo'sh bo'lsa FSM xotirada saqlanadi

    jwt_secret: str  # majburiy: .env da bo'lishi shart
    jwt_expire_minutes: int = 60 * 24 * 7

    bot_token: str = ""
    bot_username: str = ""
    telegram_auth_max_age: int = 86400

    default_trial_days: int = 30

    payment_provider: str = "test"
    payment_secret: str = ""
    public_web_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    api_internal_url: str = "http://api:8000"
    sentry_dsn: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
