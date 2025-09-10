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
    conftest.py
    test_migrations_and_seed.py
    test_splits_constraints.py
```
More modules (CSV/OFX importers, reconciliation, check printing, API & HTMX UI) will be added next.

## Quickstart
```bash
cd ledger
uv sync
uv run pytest -q
```

### Run a scratch DB locally (SQLite dev)
Default `DATABASE_URL` is `sqlite:///./dev.db`. Override for Postgres if desired:
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/ledger"
```

## CI
This repo includes a GitHub Actions workflow that installs **uv**, caches dependencies, and runs the pytest suite on push/PR.

Badge (add once pushed to GitHub):
```
[![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<you>/<repo>/actions/workflows/ci.yml)
```
