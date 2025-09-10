
from __future__ import annotations
import sys
import os
from datetime import date as _date
import argparse
from loguru import logger
from alembic import command
from alembic.config import Config
from pathlib import Path
import argparse

from ledger_app.db import SessionLocal
from ledger_app.seeds import seed_chart_of_accounts
from ledger_app.services.reversal import create_reversing_entry
from ledger_app.services.checks import void_check

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # points to 'ledger/'
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # Alembic env.py will read DATABASE_URL from env, defaulting to sqlite dev.db
    return cfg

def cmd_init_db(args) -> int:
    logger.info("Applying migrations to head…")
    command.upgrade(alembic_config(), "head")
    logger.success("Database is up-to-date.")
    return 0

def cmd_make_migration(args) -> int:
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

def cmd_reverse_tx(args) -> int:
    db = SessionLocal()
    try:
        d = _date.fromisoformat(args.date) if args.date else _date.today()
        new_id = create_reversing_entry(db, args.tx_id, d, args.memo)
        logger.success(f"Reversing transaction created: id={new_id}")
    finally:
        db.close()
    return 0

def cmd_void_check(args) -> int:
    db = SessionLocal()
    try:
        d = _date.fromisoformat(args.date) if args.date else _date.today()
        void_check(db, args.check_id, d, args.memo, not args.no_reversal)
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

    p5 = sub.add_parser("reverse-tx", help="Create reversing entry for a transaction id")
    p5.add_argument("--tx-id", type=int, required=True)
    p5.add_argument("--date", help="ISO date for reversal (default today)")
    p5.add_argument("--memo", help="Optional description")
    p5.set_defaults(func=cmd_reverse_tx)

    p6 = sub.add_parser("void-check", help="Void a check (by id) and optionally create a reversing entry")
    p6.add_argument("--check-id", type=int, required=True)
    p6.add_argument("--date", help="ISO date for reversal (default today)")
    p6.add_argument("--memo", help="Optional description")
    p6.add_argument("--no-reversal", action="store_true", help="Do not create a reversing transaction")
    p6.set_defaults(func=cmd_void_check)

    args = parser.parse_args(argv or sys.argv[1:])
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
(argv or sys.argv[1:])
    return args.func(args)

