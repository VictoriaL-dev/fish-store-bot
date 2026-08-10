from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_PORT: int = 5433
    DATABASE_NAME: str = "postgres_db"
    DATABASE_USERNAME: str = "postgres_db_user"
    DATABASE_PASSWORD: str

    ADMINER_PORT: int = 8080

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    STRAPI_TOKEN: str
    STRAPI_URL: str = "http://localhost:1337"
    STRAPI_USER_ROLE: int
    STRAPI_USER_PASSWORD: str

    TG_BOT_TOKEN: str

    @property
    def project_root(self):
        return self._get_project_root()

    @classmethod
    def _get_project_root(cls):
        return Path(__file__).resolve().parent

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
