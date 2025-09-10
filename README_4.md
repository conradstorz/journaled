# Ledger (Lean Double-Entry Bookkeeping)

A lightweight, auditable QuickBooks replacement focused on proper double-entry accounting, clean imports, reconciliation, check printing, and core financial statements.

## Features (seed)
- Chart of Accounts, Transactions, Splits (with enforced balance at post time).
- Parties + Addresses.
- Statements & Lines scaffolding.
- Alembic migrations + CLI.
- Tests and CI (uv-based).

## Quickstart
```bash
cd ledger
uv sync --group dev
uv run ledger-dev init-db
uv run pytest
```

## CI/CD
- Lint (Ruff), format check (Black), type-check (mypy), tests (pytest + coverage).
- Artifacts: coverage XML.
- Release workflow builds sdist/wheel on tag `v*`.

Badge (add once pushed to GitHub):
```
[![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<you>/<repo>/actions/workflows/ci.yml)
```
