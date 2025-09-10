from __future__ import annotations
import sys
from loguru import logger
from alembic import command
from alembic.config import Config
from pathlib import Path
import argparse

from ledger_app.db import SessionLocal
from ledger_app.seeds import seed_chart_of_accounts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    return cfg

def cmd_init_db(args) -> int:
    logger.info("Applying migrations to head…")
    command.upgrade(alembic_config(), "head")
    logger.success("Database is up-to-date.")
    return 0

def cmd_make_migration(args)) -> int:
    msg = args.message or "auto"
    logger.info(f"Creating new revision: {msg!r}")
    command.revision(alembic_config(), message=msg, autogenerate=True)
    logger.success("Revision created.")
    return 0

def cmd_downgrade(args) -> int:
    steps = args.steps or "1"
    logger.warning(f"Downgrading by {steps} step(s)…")
    command.downgrade(alembic_config(), f"-{steps}")
    logger.success("Downgrade complete.")
    return 0

def cmd_seed_coa(args) -> int:
    db = SessionLocal()
    try:
        seed_chart_of_accounts(db)
    finally:
        db.close()
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledger-dev", description="Ledger dev utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("init-db", help="Apply Alembic migrations to head")
    p1.set_defaults(func=cmd_init_db)

    p2 = sub.add_parser("rev", help="Create a new Alembic revision (autogenerate)")
    p2.add_argument("-m", "--message", help="Revision message")
    p2.set_defaults(func=cmd_make_migration)

    p3 = sub.add_parser("downgrade", help="Downgrade Alembic by N steps")
    p3.add_argument("-n", "--steps", help="Steps to downgrade (default 1)")
    p3.set_defaults(func=cmd_downgrade)

    p4 = sub.add_parser("seed-coa", help="Insert minimal chart of accounts")
    p4.set_defaults(func=cmd_seed_coa)

    args = parser.parse_args(argv or sys.argv[1:])
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
