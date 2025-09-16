from __future__ import annotations
from typing import Generator
from sqlalchemy.orm import Session
from journaled_app.db import make_sessionmaker

def get_db() -> Generator[Session, None, None]:
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
