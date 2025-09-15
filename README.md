
# Journaled (Lean Double-Entry Bookkeeping)

A lightweight, auditable QuickBooks replacement focused on proper double-entry accounting, clean imports, reconciliation, check printing, and core financial statements.

## Features (seed)
- Chart of Accounts, Transactions, Splits (with enforced balance at post time).
- Parties (payees/vendors/customers) + Addresses (foundation for check printing).
- Bank statements & lines (schema for imports and reconciliation).
- Service to post balanced transactions with Loguru logging.
- Tests (pytest) to validate double-entry enforcement.
- Modern Python stack and your preferred workflow with **uv**.

## Project Layout
```
journaled/
  pyproject.toml
  src/journaled_app/
    __init__.py
    config.py
    db.py
    models.py
    services/
      posting.py
  tests/
    test_posting.py
```
More modules (CSV/OFX importers, reconciliation, check printing, API & HTMX UI) will be added next.

## Quickstart

> Prereqs: Python 3.12+ and **uv**. No `pip` or manual venv activation needed.

```bash
# from the folder containing `journaled/`
cd journaled

# Install deps
uv sync

# Run tests
uv run pytest -q
```

### Run a scratch DB locally (SQLite dev)
Default `DATABASE_URL` is `sqlite:///./dev.db`. Override for Postgres if desired:
```bash
# Example for Postgres (adjust creds/host/db as needed)
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/journaled"
```
## New capabilities
- Post a **reversing transaction** that negates an existing transaction’s splits (and links them).
- **Void a check** by marking its status and (optionally) creating a reversing transaction.

### Using the posting service in a REPL
```bash
uv run python -q
>>> from journaled_app.db import SessionLocal, engine, Base
>>> Base.metadata.create_all(engine)  # create tables (dev only; we'll add Alembic soon)
>>> from journaled_app.models import Transaction, Split
>>> from journaled_app.services.posting import post_transaction
>>> from datetime import date
>>> from decimal import Decimal

>>> db = SessionLocal()
>>> tx = Transaction(date=date.today(), description="Seed example")
>>> s1 = Split(account_id=1, amount=Decimal("100.00"))
>>> s2 = Split(account_id=2, amount=Decimal("-100.00"))
>>> post_transaction(db, tx, [s1, s2])
>>> db.commit()
>>> db.close()
```
## CI/CD
- Lint (Ruff), format check (Black), type-check (mypy), tests (pytest + coverage).
- Artifacts: coverage XML.
- Release workflow builds sdist/wheel on tag `v*`.

Badge (add once pushed to GitHub):
```
[![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<you>/<repo>/actions/workflows/ci.yml)
```
## CLI
```bash
# Reverse a transaction (by id) with today's date
uv run journaled-dev reverse-tx --tx-id 123 --date 2025-09-08 --memo "Reversal of error"

# Void a check (by id); default creates a reversing txn dated today
uv run journaled-dev void-check --check-id 10 --date 2025-09-08 --memo "Voided check" --no-reversal  # add flag to skip reversal
```

> Note: If the original transaction has since been reconciled, consider the period impact of dating the reversal today vs. backdating — follow your accounting policy.

## Reconciliation CLI + CSV Import

Propose matches:
```bash
uv run journaled-dev reconcile-propose --account-id 1 --period-start 2025-01-01 --period-end 2025-01-31
```

Apply / unmatch:
```bash
uv run journaled-dev reconcile-apply --line-id 10 --split-id 42
uv run journaled-dev reconcile-unmatch --line-id 10
```

Status:
```bash
uv run journaled-dev reconcile-status --account-id 1 --period-start 2025-01-01 --period-end 2025-01-31
```

Import bank CSV to statement lines (creates statement if needed):
```bash
uv run journaled-dev import-csv --account-id 1       --period-start 2025-01-01 --period-end 2025-01-31       --opening 1000.00 --closing 1050.00       --csv bank.csv
```

## API
The minimal `/health` API endpoint remains included. You can add endpoints later for reversals/voids if you want to drive these via UI.

## Import OFX/QFX
```bash
uv run journaled-dev import-ofx       --account-id 1       --period-start 2025-01-01 --period-end 2025-01-31       --opening 1000.00 --closing 1050.00       --ofx bank.ofx
```
Notes:
- Dedupes by `FITID` when available, else by `(date, amount, description)`.
- Supports typical SGML-style OFX/QFX where tags may not be closed.
- Combines `<NAME>` and `<MEMO>` for description if both present.

## Logging
We use **Loguru**. At runtime, you can add sinks and log to a `logs/` directory per your preference. (A production config module will set this up; for now, we log to stdout from the tests.)

## Next Steps (planned)
1. **Alembic migrations** (init + first migration).
2. **CSV/OFX/QFX importers** with normalization + duplication control via `fitid`.
3. **Reconciliation UI** (HTMX) and matcher.
4. **Check printing** (ReportLab) with layout JSON.
5. **API & minimal HTMX UI** for Accounts/Transactions/Imports.
6. **Reports**: Balance Sheet, P&L, Cashflow (indirect), Trial Balance, GL.

## Notes
- Code style: Pydantic v2, SQLAlchemy 2.0 patterns.
- Docstrings: Sphinx-style (to be expanded).
- Packaging: `uv` only.
- Keep comments intact; extend with clarifying comments when refactoring.

---

© You. Let’s keep iterating.
