from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from loguru import logger
import os

class Base(DeclarativeBase): ...

def make_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    logger.info(f"Connecting to database: {url}")
    return create_engine(url, future=True, echo=os.getenv("SQL_ECHO","0")=="1", connect_args=connect_args)

engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
