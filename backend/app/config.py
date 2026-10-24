from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5432/invoice_keeper"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False
    auto_migrate: bool = False

    secret_key: str = "change-me-in-env"
    access_token_expire_minutes: int = 60 * 24

    admin_login: str = "admin"
    admin_password: str = "password123"

    timezone: str = "Europe/Moscow"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_api_url: str = "https://api.telegram.org"
    telegram_proxy: str = ""
    remind_days_before: int = 3
    reminder_check_interval_seconds: int = 60

    webhook_url: str = ""

    cors_origins: str = "*"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def local_today() -> date:
    return datetime.now(settings.tz).date()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
