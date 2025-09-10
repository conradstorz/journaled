# Ledger (Lean Double-Entry Bookkeeping)

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
ledger/
  pyproject.toml
  src/ledger_app/
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
# from the folder containing `ledger/`
cd ledger

# Install deps
uv sync

# Run tests
uv run pytest -q
```

### Run a scratch DB locally (SQLite dev)
The default `DATABASE_URL` is `sqlite:///./dev.db`. You can override it with PostgreSQL when ready:
```bash
# Example for Postgres (adjust creds/host/db as needed)
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/ledger"
```

### Using the posting service in a REPL
```bash
uv run python -q
>>> from ledger_app.db import SessionLocal, engine, Base
>>> Base.metadata.create_all(engine)  # create tables (dev only; we'll add Alembic soon)
>>> from ledger_app.models import Transaction, Split
>>> from ledger_app.services.posting import post_transaction
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
