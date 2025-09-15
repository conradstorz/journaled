# src/ledger_app/db.py
from __future__ import annotations

import os
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# ✅ Re-export the single, canonical Base used by all models
#    (Do NOT create another Base here.)
from .models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./journaled.db")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def make_engine(url: Optional[str] = None, *, echo: Optional[bool] = None) -> Engine:
    """
    Create a SQLAlchemy Engine.
    - Reads DATABASE_URL if url is not provided.
    - Sets SQLite connect_args to allow threaded tests/tools.
    - echo can be forced via SQL_ECHO=1.
    """
    if url is None:
        url = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

    if echo is None:
        echo = os.getenv("SQL_ECHO", "0") == "1"

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    logger.info(f"Connecting to database: {url}")
    return create_engine(url, future=True, echo=echo, connect_args=connect_args)


def make_sessionmaker(url: Optional[str] = None) -> sessionmaker:
    """
    Return a Session factory bound to the engine for the given (or env) URL.
    """
    engine = make_engine(url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = ["Base", "make_engine", "make_sessionmaker"]
