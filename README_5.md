# Ledger (Lean Double-Entry Bookkeeping)

This build adds **void checks** and **reversing entries** for already-posted transactions.

## New capabilities
- Post a **reversing transaction** that negates an existing transaction’s splits (and links them).
- **Void a check** by marking its status and (optionally) creating a reversing transaction.

## Quickstart
```bash
cd ledger
uv sync --group dev
uv run ledger-dev init-db
uv run ledger-dev seed-coa  # optional: blank chart only
```

## CLI
```bash
# Reverse a transaction (by id) with today's date
uv run ledger-dev reverse-tx --tx-id 123 --date 2025-09-08 --memo "Reversal of error"

# Void a check (by id); default creates a reversing txn dated today
uv run ledger-dev void-check --check-id 10 --date 2025-09-08 --memo "Voided check" --no-reversal  # add flag to skip reversal
```

> Note: If the original transaction has since been reconciled, consider the period impact of dating the reversal today vs. backdating — follow your accounting policy.

## API
The minimal `/health` API endpoint remains included. You can add endpoints later for reversals/voids if you want to drive these via UI.
