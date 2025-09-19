from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from pathlib import Path
from typing import Optional, List

import typer
from loguru import logger
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError, OperationalError

from journaled_app.db import SessionLocal
from journaled_app.seeds import seed_chart_of_accounts
from journaled_app.services.reversal import create_reversing_entry
from journaled_app.services.checks import void_check as void_check_service
from journaled_app.services.import_csv import import_statement_csv
from journaled_app.services.import_ofx import import_ofx as import_ofx_service

# Choose ONE reconcile API; using the pluralized one:
from journaled_app.services.reconcile import (
    ReconcileParams,
    propose_matches,
    apply_match,
    unmatch_matches,
    get_reconcile_status,
)

# ---- Logger & Typer app must be defined BEFORE any decorators ----
logger = logger.opt(colors=True)
app = typer.Typer(no_args_is_help=True)

@app.callback()
def _banner(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the CLI version and exit",
        is_eager=True,
    ),
):
    logger.info(f"Callback triggered. version={version}")
    if version:
        try:
            import importlib.metadata
            v = importlib.metadata.version("journaled-app")
            logger.info(f"Version lookup succeeded: {v}")
        except Exception as e:
            logger.error(f"Version lookup failed: {e}")
            v = "unknown"
        typer.echo(f"Journaled CLI version: {v}")
        raise typer.Exit()
    logger.info("Journaled CLI starting up…")

# ---- Alembic ini discovery + config ----
def _find_alembic_ini(start: Path) -> Path:
    for p in [start, *start.parents]:
        candidate = p / "alembic.ini"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("alembic.ini not found from " + str(start))

ALEMBIC_INI = _find_alembic_ini(Path(__file__).resolve())

def alembic_config(db_url: Optional[str] = None) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg

# ---- Friendly validators ----
def _parse_date(label: str, s: str) -> _date:
    try:
        return _date.fromisoformat(s)
    except Exception as e:
        raise typer.BadParameter(f"{label} must be YYYY-MM-DD, got {s!r}") from e

def _parse_money(label: str, s: str) -> Decimal:
    try:
        return Decimal(s)
    except Exception as e:
        raise typer.BadParameter(f"{label} must be a decimal number, got {s!r}") from e

def _params_from_cli(
    account_id: int,
    period_start: str,
    period_end: str,
    amount_tolerance: str,
    date_window: int,
) -> ReconcileParams:
    return ReconcileParams(
        account_id=account_id,
        period_start=_parse_date("period-start", period_start),
        period_end=_parse_date("period-end", period_end),
        amount_tolerance=_parse_money("amount-tolerance", amount_tolerance),
        date_window_days=int(date_window),
    )

# -------------------------
# reconcile-propose
# -------------------------
@app.command("reconcile-propose")
def reconcile_propose(
    account_id: int = typer.Option(..., help="Internal account id to reconcile"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="Allowed difference when matching amounts"),
    date_window: int = typer.Option(3, help="Days to search before/after for near-date matches"),
):
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)
    db = SessionLocal()
    try:
        logger.info(
            "Proposing matches for account {} from {} to {} (±{} days, tol={})",
            params.account_id, params.period_start, params.period_end,
            params.date_window_days, params.amount_tolerance,
        )
        proposals = propose_matches(db, params)
        if not proposals:
            logger.warning("No match proposals found.")
            return
        for p in proposals:
            logger.info(
                "proposal line_id={} -> split_id={} score={} reason={}",
                getattr(p, "line_id", None),
                getattr(p, "split_id", None),
                getattr(p, "score", None),
                getattr(p, "reason", None),
            )
        logger.success("Proposed {} match(es).", len(proposals))
    finally:
        db.close()

# -------------------------
# reconcile-apply
# -------------------------
@app.command("reconcile-apply")
def reconcile_apply(
    account_id: int = typer.Option(..., help="Internal account id to reconcile"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="Allowed difference when matching amounts"),
    date_window: int = typer.Option(3, help="Days to search before/after for near-date matches"),
    match_id: List[int] = typer.Option(
        None,
        "--match-id",
        help="Apply only these proposal IDs (repeatable). If omitted, applies all current proposals in the window.",
    ),
    dry_run: bool = typer.Option(False, help="Show how many would apply without writing changes"),
):
    """
    Apply previously proposed matches (all in window, or just the provided --match-id values).
    """
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)

    db = SessionLocal()
    try:
        logger.info(
            "Applying matches for account {} from {} to {} (±{} days, tol={}){}",
            params.account_id,
            params.period_start,
            params.period_end,
            params.date_window_days,
            params.amount_tolerance,
            " [dry-run]" if dry_run else "",
        )

        # Your service can interpret dry_run or you can just skip commit via transaction management.
        # Here we assume the service supports a dry-run by simply not committing when requested.
        if dry_run:
            applied = 0
            logger.info("Dry run complete. (No changes written.)")
        else:
            applied = apply_match(db, params, match_ids=match_id or None)
        logger.success("Applied {} match(es).", applied)
    finally:
        db.close()

# -------------------------
# reconcile-unmatch
# -------------------------
@app.command("reconcile-unmatch")
def reconcile_unmatch(
    account_id: int = typer.Option(..., help="Internal account id to operate on"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="Not used for unmatching; kept for CLI symmetry"),
    date_window: int = typer.Option(3, help="Not used for unmatching; kept for CLI symmetry"),
    split_id: List[int] = typer.Option(None, "--split-id", help="Unmatch specific split id(s)"),
    line_id: List[int] = typer.Option(None, "--line-id", help="Unmatch specific line id(s)"),
    all_: bool = typer.Option(False, "--all", help="Unmatch all in the given window"),
):
    """
    Remove existing matches. Provide --split-id and/or --line-id for targeted unmatch,
    or --all to clear all matches within the period window.
    """
    if not any([split_id, line_id, all_]):
        raise typer.BadParameter("Specify at least one of --split-id, --line-id, or --all.")

    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)

    db = SessionLocal()
    try:
        logger.info(
            "Unmatching in account {} from {} to {} (targets: split_ids={}, line_ids={}, all={})",
            params.account_id,
            params.period_start,
            params.period_end,
            split_id or [],
            line_id or [],
            all_,
        )

        count = unmatch_matches(
            db,
            params,
            split_ids=(split_id or None),
            line_ids=(line_id or None),
            all_=bool(all_),
        )

        if count == 0:
            logger.warning("No matches were removed.")
        else:
            logger.success("Removed {} match(es).", count)
    finally:
        db.close()

# -------------------------
# reconcile-status
# -------------------------
@app.command("reconcile-status")
def reconcile_status(
    account_id: int = typer.Option(..., help="Internal account id to summarize"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="For completeness; services may use this in stats"),
    date_window: int = typer.Option(3, help="For completeness; services may use this in stats"),
):
    """
    Show a summary of reconciliation status for the window.
    """
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)

    db = SessionLocal()
    try:
        status = get_reconcile_status(db, params)
        # Expecting attributes like: total_lines, total_splits, matched_pairs, unmatched_lines, unmatched_splits, balance_diff
        logger.info("Total lines: {}", getattr(status, "total_lines", None))
        logger.info("Total splits: {}", getattr(status, "total_splits", None))
        logger.info("Matched pairs: {}", getattr(status, "matched_pairs", None))
        logger.info("Unmatched lines: {}", getattr(status, "unmatched_lines", None))
        logger.info("Unmatched splits: {}", getattr(status, "unmatched_splits", None))
        logger.info("Balance difference: {}", getattr(status, "balance_diff", None))
        logger.success("Status OK.")
    finally:
        db.close()

# Begin typer command declarations

@app.command("seed-coa")
def seed_coa(
    migrate: bool = typer.Option(True, "--migrate/--no-migrate", help="Run alembic migrations first."),
    idempotent: bool = typer.Option(True, "--idempotent/--no-idempotent", help="Skip existing accounts if possible."),
    dry_run: bool = typer.Option(False, help="Prepare seed but do not persist changes."),
    db: Optional[str] = typer.Option(None, help="DB URL or SQLite path to target (overrides alembic.ini)"),
):
    """
    Seed the database with a minimal chart of accounts, safely.
    """
    if migrate:
        logger.info(f"Ensuring schema is up to date (alembic upgrade head) on DB: {db or 'alembic.ini setting'}")
        command.upgrade(alembic_config(db), "head")
        logger.success("Migrations are up to date.")

    # If you want this command to honor --db at the session level, you can
    # implement a SessionLocal factory that reads DATABASE_URL env, then:
    #   if db: os.environ["DATABASE_URL"] = db
    # and let SessionLocal() pick that up. Otherwise, keep as-is.
    sess = SessionLocal()
    try:
        logger.info(f"Seeding chart of accounts (idempotent={idempotent}, dry_run={dry_run})…")

        # Use a SAVEPOINT-style transaction so dry-run can roll back everything regardless of what the seeder does.
        if dry_run:
            sess.begin()               # outer transaction
            sess.begin_nested()        # savepoint for safe rollback

        try:
            with sess.begin():         # atomic write (or nested within dry-run)
                try:
                    result = seed_chart_of_accounts(sess, idempotent=idempotent, dry_run=dry_run)
                except TypeError:
                    result = seed_chart_of_accounts(sess)
        except Exception:
            # Make sure we roll back the nested transaction if dry-run or on any error.
            if dry_run:
                sess.rollback()
            raise

        if dry_run:
            sess.rollback()  # discard everything
            total = getattr(result, "total", None)
            if total is not None:
                logger.success(f"DRY RUN: {total} account(s) would be ensured.")
            else:
                logger.success("DRY RUN: seeding completed with no writes.")
        else:
            created = getattr(result, "created", None)
            skipped = getattr(result, "skipped", None)
            if created is not None or skipped is not None:
                logger.success(f"Seeded chart of accounts. created={created}, skipped={skipped}")
            else:
                logger.success("Seeded chart of accounts.")
    except IntegrityError as e:
        msg = str(e).splitlines()[0]
        logger.error(f"Seeding failed due to duplicate data (IntegrityError). Try --idempotent or clean rows. Details: {msg}")
        raise typer.Exit(code=1)
    except OperationalError as e:
        msg = str(e).splitlines()[0]
        logger.error(f"Database not ready (OperationalError). Check DB URL/migrations. Details: {msg}")
        raise typer.Exit(code=2)
    finally:
        sess.close()

@app.command()
def init_db(db: Optional[str] = typer.Option(None, help="DB URL or SQLite path (overrides alembic.ini)")):
    logger.info(f"Applying migrations to DB: {db or 'alembic.ini setting'}")
    # If db is a SQLite file path, ensure the file is created by connecting
    db_url = db
    if db and (db.startswith("sqlite:///") or db.endswith(".db")):
        # Normalize to URL if needed
        if not db.startswith("sqlite:///"):
            db_url = f"sqlite:///{db}"
        from sqlalchemy import create_engine
        engine = create_engine(db_url, future=True)
        # Connect to create the file
        with engine.connect():
            pass
        engine.dispose()
    command.upgrade(alembic_config(db), "head")
    logger.success("Migrations applied.")

@app.command()
def rev(message: str = typer.Option("auto", "-m", "--message", help="Revision message")):
    logger.info(f"Creating new revision: {message!r}")
    command.revision(alembic_config(None), message=message, autogenerate=True)
    logger.success("Revision created.")

@app.command()
def downgrade(steps: str = typer.Option("1", "-n", "--steps", help="Steps to downgrade (default 1)")):
    logger.warning(f"Downgrading by {steps} step(s)…")
    command.downgrade(alembic_config(None), f"-{steps}")
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

@app.command("void-check")
def void_check(
    check_id: int = typer.Option(..., help="Check ID to void"),
    date: str = typer.Option(None, help="ISO date for reversal (default today)"),
    memo: str = typer.Option(None, help="Optional description"),
    no_reversal: bool = typer.Option(False, help="Do not create a reversing transaction"),
):
    """Void a check (optionally without a reversing entry)."""
    db = SessionLocal()
    try:
        d = _parse_date("date", date) if date else _date.today()
        void_check_service = void_check  # if name clashes, import as alias at top: `from ... import void_check as void_check_service`
        void_check_service(db, check_id, d, memo, not no_reversal)
        logger.success(f"Check {check_id} voided.{'' if no_reversal else ' Reversal created.'}")
    finally:
        db.close()

@app.command()
def import_csv(
    account_id: int = typer.Option(..., help="Account ID"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD"),
    opening: str = typer.Option(..., help="Opening balance"),
    closing: str = typer.Option(..., help="Closing balance"),
    csv_path: str = typer.Option(..., "--csv", help="Path to CSV file"),
    no_header: bool = typer.Option(False, help="CSV has no header row"),
    date_format: str = typer.Option("%Y-%m-%d", help="Python strptime format for dates"),
    date_col: str = typer.Option("date", help="Date column name"),
    amount_col: str = typer.Option("amount", help="Amount column name"),
    desc_col: str = typer.Option("description", help="Description column name"),
    fitid_col: str = typer.Option("fitid", help="FITID column name"),
):
    db = SessionLocal()
    try:
        period_start_dt = _parse_date("period_start", period_start)
        period_end_dt = _parse_date("period_end", period_end)
        opening_dec = _parse_money("opening", opening)
        closing_dec = _parse_money("closing", closing)
        created_stmt_id, line_count = import_statement_csv(
            db=db,
            account_id=account_id,
            period_start=period_start_dt,
            period_end=period_end_dt,
            opening_bal=opening_dec,
            closing_bal=closing_dec,
            csv_path=csv_path,
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

@app.command("import-ofx")
def import_ofx_cmd(
    account_id: int = typer.Option(..., help="Account ID"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD"),
    opening: str = typer.Option(..., help="Opening balance"),
    closing: str = typer.Option(..., help="Closing balance"),
    ofx: str = typer.Option(..., help="Path to OFX/QFX file"),
):
    db = SessionLocal()
    try:
        period_start_dt = _parse_date("period_start", period_start)
        period_end_dt = _parse_date("period_end", period_end)
        opening_dec = _parse_money("opening", opening)
        closing_dec = _parse_money("closing", closing)
        stmt_id, count = import_ofx_service(
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
@app.command("reconcile-apply")
def reconcile_apply(
    account_id: int = typer.Option(..., help="Internal account id to reconcile"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="Allowed difference when matching amounts"),
    date_window: int = typer.Option(3, help="Days to search before/after for near-date matches"),
    match_id: List[int] = typer.Option(None, "--match-id", help="Apply only these proposal IDs (repeatable)"),
    dry_run: bool = typer.Option(False, help="Show how many would apply without writing changes"),
):
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)
    db = SessionLocal()
    try:
        logger.info(
            "Applying matches for account {} from {} to {} (±{} days, tol={}){}",
            params.account_id, params.period_start, params.period_end,
            params.date_window_days, params.amount_tolerance,
            " [dry-run]" if dry_run else "",
        )
        if dry_run:
            applied = 0
            logger.info("Dry run complete. (No changes written.)")
        else:
            applied = apply_match(db, params, match_ids=(match_id or None))
        logger.success("Applied {} match(es).", applied)
    finally:
        db.close()

@app.command("reconcile-unmatch")
def reconcile_unmatch(
    account_id: int = typer.Option(..., help="Internal account id to operate on"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="Kept for symmetry"),
    date_window: int = typer.Option(3, help="Kept for symmetry"),
    split_id: List[int] = typer.Option(None, "--split-id", help="Unmatch specific split id(s)"),
    line_id: List[int] = typer.Option(None, "--line-id", help="Unmatch specific line id(s)"),
    all_: bool = typer.Option(False, "--all", help="Unmatch all in the given window"),
):
    if not any([split_id, line_id, all_]):
        raise typer.BadParameter("Specify at least one of --split-id, --line-id, or --all.")
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)
    db = SessionLocal()
    try:
        logger.info(
            "Unmatching in account {} from {} to {} (targets: split_ids={}, line_ids={}, all={})",
            params.account_id, params.period_start, params.period_end,
            split_id or [], line_id or [], all_,
        )
        count = unmatch_matches(
            db, params,
            split_ids=(split_id or None), line_ids=(line_id or None), all_=bool(all_),
        )
        if count == 0:
            logger.warning("No matches were removed.")
        else:
            logger.success("Removed {} match(es).", count)
    finally:
        db.close()

@app.command("reconcile-status")
def reconcile_status(
    account_id: int = typer.Option(..., help="Internal account id to summarize"),
    period_start: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    period_end: str = typer.Option(..., help="YYYY-MM-DD inclusive"),
    amount_tolerance: str = typer.Option("0.00", help="For completeness"),
    date_window: int = typer.Option(3, help="For completeness"),
):
    params = _params_from_cli(account_id, period_start, period_end, amount_tolerance, date_window)
    db = SessionLocal()
    try:
        s = get_reconcile_status(db, params)
        logger.info("Total lines: {}", getattr(s, "total_lines", None))
        logger.info("Total splits: {}", getattr(s, "total_splits", None))
        logger.info("Matched pairs: {}", getattr(s, "matched_pairs", None))
        logger.info("Unmatched lines: {}", getattr(s, "unmatched_lines", None))
        logger.info("Unmatched splits: {}", getattr(s, "unmatched_splits", None))
        logger.info("Balance difference: {}", getattr(s, "balance_diff", None))
        logger.success("Status OK.")
    finally:
        db.close()

# Entry point for direct CLI execution
if __name__ == "__main__":
    app()
