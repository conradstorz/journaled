from __future__ import annotations
from datetime import date as _date
from decimal import Decimal
from loguru import logger
from alembic import command
from alembic.config import Config
from pathlib import Path

from journaled_app.db import SessionLocal
from journaled_app.seeds import seed_chart_of_accounts
from journaled_app.services.reversal import create_reversing_entry
from journaled_app.services.checks import void_check
from journaled_app.services.reconcile import ReconcileParams, propose_matches, apply_match, unmatch, status
from journaled_app.services.import_csv import import_statement_csv
from journaled_app.services.import_ofx import import_ofx

# --- Project root and Alembic config ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # points to 'journaled/' project root
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"          # Path to Alembic configuration file

def alembic_config() -> Config:
    """
    Returns an Alembic Config object for migration commands.
    Alembic will read DATABASE_URL from the environment.
    """
    cfg = Config(str(ALEMBIC_INI))
    return cfg


@app.command()
def init_db(db: Optional[str] = typer.Option(None, help="Path to SQLite DB file (overrides DATABASE_URL)")):
    """
    Applies Alembic migrations to the database.
    """
    logger.info(f"Applying migrations to DB: {db or 'default'}")
    command.upgrade(alembic_config(), "head")
    logger.success("Migrations applied.")

@app.command()
def seed_coa():
    """
    Seeds the database with a minimal chart of accounts.
    """
    db_session = SessionLocal()
    try:
        seed_chart_of_accounts(db_session)
    finally:
        db_session.close()
    logger.success("Seeded chart of accounts.")

@app.command()
def rev(message: str = typer.Option("auto", "-m", "--message", help="Revision message")):
    """
    Creates a new Alembic migration revision, autogenerating changes.
    """
    logger.info(f"Creating new revision: {message!r}")
    command.revision(alembic_config(), message=message, autogenerate=True)
    logger.success("Revision created.")

@app.command()
def downgrade(steps: str = typer.Option("1", "-n", "--steps", help="Steps to downgrade (default 1)")):
    """
    Downgrades the database schema by a given number of steps.
    """
    logger.warning(f"Downgrading by {steps} step(s)…")
    command.downgrade(alembic_config(), f"-{steps}")
    logger.success("Downgrade complete.")

@app.command()
def reverse_tx(
    tx_id: int = typer.Option(..., help="Transaction ID to reverse"),
    date: str = typer.Option(None, help="ISO date for reversal (default today)"),
    memo: str = typer.Option(None, help="Optional description")
):
    """
    Creates a reversing entry for a given transaction ID.
    Optionally takes a date and memo for the reversal.
    """
    db = SessionLocal()
    try:
        d = _date.fromisoformat(date) if date else _date.today()
        new_id = create_reversing_entry(db, tx_id, d, memo)
        logger.success(f"Reversing transaction created: id={new_id}")
    finally:
        db.close()

@app.command()
def void_check_cmd(
    check_id: int = typer.Option(..., help="Check ID to void"),
    date: str = typer.Option(None, help="ISO date for reversal (default today)"),
    memo: str = typer.Option(None, help="Optional description"),
    no_reversal: bool = typer.Option(False, help="Do not create a reversing transaction")
):
    """
    Voids a check by ID and optionally creates a reversing transaction.
    """
    db = SessionLocal()
    try:
        d = _date.fromisoformat(date) if date else _date.today()
        void_check(db, check_id, d, memo, not no_reversal)
        logger.success(f"Check {check_id} voided.{' Reversal created.' if not no_reversal else ''}")
    finally:
        db.close()

@app.command()
def import_csv(
    account_id: int = typer.Option(..., help="Account ID"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD"),
    opening: str = typer.Option(..., help="Opening balance"),
    closing: str = typer.Option(..., help="Closing balance"),
    csv: str = typer.Option(..., help="Path to CSV file"),
    no_header: bool = typer.Option(False, help="CSV has no header row"),
    date_format: str = typer.Option("%Y-%m-%d", help="Python strptime format for dates"),
    date_col: str = typer.Option("date", help="Date column name"),
    amount_col: str = typer.Option("amount", help="Amount column name"),
    desc_col: str = typer.Option("description", help="Description column name"),
    fitid_col: str = typer.Option("fitid", help="FITID column name")
):
    """
    Imports a bank statement from a CSV file into statement_lines.
    Creates or finds the corresponding Statement.
    """
    db = SessionLocal()
    try:
        period_start_dt = _date.fromisoformat(period_start)
        period_end_dt = _date.fromisoformat(period_end)
        opening_dec = Decimal(opening)
        closing_dec = Decimal(closing)
        created_stmt_id, line_count = import_statement_csv(
            db=db,
            account_id=account_id,
            period_start=period_start_dt,
            period_end=period_end_dt,
            opening_bal=opening_dec,
            closing_bal=closing_dec,
            csv_path=csv,
            date_format=date_format,
            has_header=(not no_header),
            date_col=date_col,
            amount_col=amount_col,
            desc_col=desc_col,
            fitid_col=fitid_col,
        )
        logger.success(f"Imported {line_count} lines into statement id={created_stmt_id}")
    finally:
        db.close()

@app.command()
def import_ofx(
    account_id: int = typer.Option(..., help="Account ID"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD"),
    opening: str = typer.Option(..., help="Opening balance"),
    closing: str = typer.Option(..., help="Closing balance"),
    ofx: str = typer.Option(..., help="Path to OFX/QFX file")
):
    """
    Imports a bank statement from an OFX/QFX file into statement_lines.
    """
    db = SessionLocal()
    try:
        period_start_dt = _date.fromisoformat(period_start)
        period_end_dt = _date.fromisoformat(period_end)
        opening_dec = Decimal(opening)
        closing_dec = Decimal(closing)
        stmt_id, count = import_ofx(
            db=db,
            account_id=account_id,
            period_start=period_start_dt,
            period_end=period_end_dt,
            opening_bal=opening_dec,
            closing_bal=closing_dec,
            ofx_path=ofx,
        )
        logger.success(f"Imported {count} lines into statement id={stmt_id}")
    finally:
        db.close()

# --- Reconciliation commands ---

def cmd_reconcile_propose(args) -> int:
    """
    Proposes matches between statement lines and splits for a given account and period.
    Prints proposed matches with scores and reasons.
    """
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
    """
    Applies a proposed match between a statement line and a split.
    """
    db = SessionLocal()
    try:
        apply_match(db, args.line_id, args.split_id)
        print("ok")
    finally:
        db.close()
    return 0

def cmd_reconcile_unmatch(args) -> int:
    """
    Unmatches a statement line from any split it is currently matched to.
    """
    db = SessionLocal()
    try:
        unmatch(db, args.line_id)
        print("ok")
    finally:
        db.close()
    return 0

def cmd_reconcile_status(args) -> int:
    """
    Shows reconciliation status for a statement period, including balances and match counts.
    """
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
