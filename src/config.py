"""Central configuration: loads DB settings from .env and builds a SQLAlchemy engine.

Single source of connection truth so no module hardcodes credentials or paths.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Project root = two levels up from this file (src/config.py -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

load_dotenv(PROJECT_ROOT / ".env")


def _require(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {var}. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


def database_url() -> str:
    """Build the SQLAlchemy connection URL from environment variables."""
    user = _require("DB_USER")
    password = _require("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = _require("DB_NAME")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the project database."""
    return create_engine(database_url(), future=True)
