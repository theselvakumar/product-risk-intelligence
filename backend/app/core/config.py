import os
from typing import List, Union
from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DRISHTI Compliance Risk Intelligence Platform"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # JWT Authentication Security
    SECRET_KEY: str = "drishti-regulatory-secret-key-change-in-production-2026-fssai"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Web Intelligence Configuration (Phase C2)
    WEB_INTELLIGENCE_ENABLED: bool = True
    SEARCH_PROVIDER: str = "duckduckgo"  # duckduckgo, searxng, custom, mock
    SEARCH_API_KEY: str | None = None
    SEARCH_API_ENDPOINT: str | None = None
    MAX_SEARCH_RESULTS: int = 3
    MAX_PAGES_SCRAPED: int = 2
    SCRAPER_TIMEOUT_SECONDS: float = 6.0
    SCRAPER_MAX_CONTENT_BYTES: int = 1_000_000  # 1MB safe cap
    SCRAPER_USER_AGENT: str = "DRISHTI-Regulatory-Surveillance-Bot/1.0 (+https://fssai.gov.in)"

    # Database configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "drishti"

    DATABASE_URL: str | None = None

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
            if self.DATABASE_URL.startswith("sqlite+aiosqlite://"):
                return self.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            if self.DATABASE_URL.startswith("sqlite://") and not self.DATABASE_URL.startswith("sqlite+aiosqlite://"):
                return self.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
