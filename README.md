
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

# Journaled: Lean Double-Entry Bookkeeping

Welcome to Journaled! This is a modern, lightweight, and auditable double-entry accounting system designed to be a clean bookkeeping
option for developers, bookkeepers, and small businesses.

## Why Journaled?
- True double-entry enforcement (no cheating with unbalanced transactions)
- Clean imports (CSV, OFX/QFX)
- Reconciliation tools
- Check printing
- Core financial statements
- Modern Python stack (SQLAlchemy 2.0, Pydantic v2, Alembic, Loguru)

---

## Getting Started (Newbie Friendly)

### Prerequisites
- Python 3.12+
- [uv](https://astral.sh/uv/) (fast Python package/dependency manager)
  - If you need help installing `uv`, see the [Astral homepage](https://astral.sh/uv/).

### Setup Steps
1. **Clone the repo and enter the project folder:**
   ```bash
   git clone https://github.com/conradstorz/journaled.git
   cd journaled
   ```
2. **Install dependencies:**
   ```bash
   uv sync
   ```
3. **Run all tests (with per-test DB isolation and migrations):**
   ```bash
   uv run pytest -q
   ```
   - All tests should pass! If not, check your Python version and `uv` install.

---

## Project Structure
```
journaled/
  pyproject.toml
  src/journaled_app/
    models.py
    services/
      posting.py
      import_csv.py
      import_ofx.py
      ...
  tests/
    test_posting.py
    test_import_csv.py
    ...
```

---

## Running Journaled

### Default Database
  ```bash
  export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/journaled"
  ```

### CLI Usage

---

## Developer Tips
- All tests use per-test DB isolation and run Alembic migrations automatically.
- Logging is via Loguru (stdout by default).
- Coverage and CI/CD are set up (pytest, Ruff, Black, mypy).
- If you see errors about missing tables, check your Alembic migration setup and `DATABASE_URL`.

---

## API & Extensibility
- Minimal `/health` endpoint included.
- Extend with more endpoints for reversals, voids, imports, etc.

---

## Next Steps & Roadmap
1. More importers (CSV/OFX/QFX normalization, deduplication)
2. Reconciliation UI (HTMX)
3. Check printing (ReportLab)
4. API & minimal HTMX UI for Accounts/Transactions/Imports
5. Financial reports: Balance Sheet, P&L, Cashflow, Trial Balance, GL

---

## Resources
- [uv documentation & install help](https://astral.sh/uv/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [Loguru](https://loguru.readthedocs.io/)

---
If you find this useful please fork and make it better!
I hope to be able to accept help from the community on this project.
© 2025 by Conrad Storz. Let’s keep iterating and improving Journaled!
