"""Configuration for the Tushare ingestion pipeline.

The token and gateway URL are read from the environment (or a local .env
file at the project root). They are never hardcoded in source.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    token: str = field(default_factory=lambda: os.environ.get("TUSHARE_TOKEN", ""))
    # Purchased third-party gateway; must override the default Tushare URL.
    http_url: str = field(
        default_factory=lambda: os.environ.get("TUSHARE_HTTP_URL", "https://tuaremax.top")
    )
    db_path: Path = PROJECT_ROOT / "data" / "bme.duckdb"
    # Conservative rate limit: max calls per minute against the gateway.
    max_calls_per_minute: int = int(os.environ.get("TUSHARE_MAX_CPM", "30"))
    retry_attempts: int = 3
    retry_backoff_seconds: float = 5.0


def get_settings() -> Settings:
    return Settings()
