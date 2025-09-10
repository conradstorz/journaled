from __future__ import annotations
import sys
from datetime import date as _date
import argparse
from decimal import Decimal
from loguru import logger
from alembic import command
from alembic.config import Config
from pathlib import Path

from ledger_app.db import SessionLocal
from ledger_app.seeds import seed_chart_of_accounts
from ledger_app.services.reversal import create_reversing_entry
from ledger_app.services.checks import void_check
from ledger_app.services.reconcile import ReconcileParams, propose_matches, apply_match, unmatch, status
from ledger_app.services.import_csv import import_statement_csv
from ledger_app.services.import_ofx import import_ofx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))

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

# Reconcile commands
def cmd_reconcile_propose(args) -> int:
    db = SessionLocal()
    try:
        params = ReconcileParams(
            account_id=args.account_id,
            period_start=_date.fromisoformat(args.period_start),
            period_end=_date.fromisoformat(args.period_end),
            amount_tolerance=Decimal(args.amount_tolerance),
            date_window_days=int(args.date_window),
        )
        proposals = propose_matches(db, params)
        for p in proposals:
            print(f"line={p.line_id} -> split={p.split_id} score={p.score} reason={p.reason}")
    finally:
        db.close()
    return 0

def cmd_reconcile_apply(args) -> int:
    db = SessionLocal()
    try:
        apply_match(db, args.line_id, args.split_id)
        print("ok")
    finally:
        db.close()
    return 0

def cmd_reconcile_unmatch(args) -> int:
    db = SessionLocal()
    try:
        unmatch(db, args.line_id)
        print("ok")
    finally:
        db.close()
    return 0

def cmd_reconcile_status(args) -> int:
    db = SessionLocal()
    try:
        params = ReconcileParams(
            account_id=args.account_id,
            period_start=_date.fromisoformat(args.period_start),
            period_end=_date.fromisoformat(args.period_end),
            amount_tolerance=Decimal(args.amount_tolerance),
            date_window_days=int(args.date_window),
        )
        s = status(db, params)
        print(f"opening={s.opening_bal} closing={s.closing_bal} stmt_delta={s.stmt_delta} "
              f"book_delta={s.book_delta} diff={s.difference} "
              f"matched_lines={s.matched_lines} unmatched_lines={s.unmatched_lines}")
    finally:
        db.close()
    return 0

def cmd_import_csv(args) -> int:
    db = SessionLocal()
    try:
        period_start = _date.fromisoformat(args.period_start)
        period_end = _date.fromisoformat(args.period_end)
        opening = Decimal(args.opening)
        closing = Decimal(args.closing)
        created_stmt_id, line_count = import_statement_csv(
            db=db,
            account_id=args.account_id,
            period_start=period_start,
            period_end=period_end,
            opening_bal=opening,
            closing_bal=closing,
            csv_path=args.csv,
            date_format=args.date_format,
            has_header=(not args.no_header),
            date_col=args.date_col,
            amount_col=args.amount_col,
            desc_col=args.desc_col,
            fitid_col=args.fitid_col,
        )
        logger.success(f"Imported {line_count} lines into statement id={created_stmt_id}")
    finally:
        db.close()
    return 0

def cmd_import_ofx(args) -> int:
    db = SessionLocal()
    try:
        period_start = _date.fromisoformat(args.period_start)
        period_end = _date.fromisoformat(args.period_end)
        opening = Decimal(args.opening)
        closing = Decimal(args.closing)
        stmt_id, count = import_ofx(
            db=db,
            account_id=args.account_id,
            period_start=period_start,
            period_end=period_end,
            opening_bal=opening,
            closing_bal=closing,
            ofx_path=args.ofx,
        )
        logger.success(f"Imported {count} lines into statement id={stmt_id}")
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

    # Reconcile
    p7 = sub.add_parser("reconcile-propose", help="Propose matches for a statement period")
    p7.add_argument("--account-id", type=int, required=True)
    p7.add_argument("--period-start", required=True)
    p7.add_argument("--period-end", required=True)
    p7.add_argument("--amount-tolerance", default="0.01")
    p7.add_argument("--date-window", default="3")
    p7.set_defaults(func=cmd_reconcile_propose)

    p8 = sub.add_parser("reconcile-apply", help="Apply a match: line -> split")
    p8.add_argument("--line-id", type=int, required=True)
    p8.add_argument("--split-id", type=int, required=True)
    p8.set_defaults(func=cmd_reconcile_apply)

    p9 = sub.add_parser("reconcile-unmatch", help="Unmatch a statement line")
    p9.add_argument("--line-id", type=int, required=True)
    p9.set_defaults(func=cmd_reconcile_unmatch)

    p10 = sub.add_parser("reconcile-status", help="Show reconciliation status for a statement")
    p10.add_argument("--account-id", type=int, required=True)
    p10.add_argument("--period-start", required=True)
    p10.add_argument("--period-end", required=True)
    p10.add_argument("--amount-tolerance", default="0.01")
    p10.add_argument("--date-window", default="3")
    p10.set_defaults(func=cmd_reconcile_status)

    # Import CSV
    p11 = sub.add_parser("import-csv", help="Import a bank CSV into statement_lines (creates/finds Statement)")
    p11.add_argument("--account-id", type=int, required=True)
    p11.add_argument("--period-start", required=True, help="YYYY-MM-DD")
    p11.add_argument("--period-end", required=True, help="YYYY-MM-DD")
    p11.add_argument("--opening", required=True, help="Opening balance for the statement")
    p11.add_argument("--closing", required=True, help="Closing balance for the statement")
    p11.add_argument("--csv", required=True, help="Path to CSV file")
    p11.add_argument("--no-header", action="store_true", help="CSV has no header row")
    p11.add_argument("--date-format", default="%Y-%m-%d", help="Python strptime format for dates")
    p11.add_argument("--date-col", default="date")
    p11.add_argument("--amount-col", default="amount")
    p11.add_argument("--desc-col", default="description")
    p11.add_argument("--fitid-col", default="fitid")
    p11.set_defaults(func=cmd_import_csv)

    # Import OFX/QFX
    p12 = sub.add_parser("import-ofx", help="Import an OFX/QFX file into statement_lines")
    p12.add_argument("--account-id", type=int, required=True)
    p12.add_argument("--period-start", required=True, help="YYYY-MM-DD")
    p12.add_argument("--period-end", required=True, help="YYYY-MM-DD")
    p12.add_argument("--opening", required=True, help="Opening balance for the statement")
    p12.add_argument("--closing", required=True, help="Closing balance for the statement")
    p12.add_argument("--ofx", required=True, help="Path to OFX/QFX file")
    p12.set_defaults(func=cmd_import_ofx)

    args = parser.parse_args(argv or sys.argv[1:])
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
