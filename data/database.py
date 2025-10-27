"""Database utilities for the scraping plug-in."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_FILENAME = os.environ.get("SCRAPER_DB_FILENAME", "scraper.db")
DB_PATH = Path(DB_FILENAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """Initialise the database and create tables when necessary."""
    from data import models  # noqa: WPS433 (lazy import to avoid circular dependency)

    Base.metadata.create_all(bind=engine)


__all__ = ["SessionLocal", "Base", "init_db"]
