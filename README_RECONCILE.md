## Reconciliation CLI + CSV Import

Propose matches:
```bash
uv run ledger-dev reconcile-propose --account-id 1 --period-start 2025-01-01 --period-end 2025-01-31
```

Apply / unmatch:
```bash
uv run ledger-dev reconcile-apply --line-id 10 --split-id 42
uv run ledger-dev reconcile-unmatch --line-id 10
```

Status:
```bash
uv run ledger-dev reconcile-status --account-id 1 --period-start 2025-01-01 --period-end 2025-01-31
```

Import bank CSV to statement lines (creates statement if needed):
```bash
uv run ledger-dev import-csv --account-id 1       --period-start 2025-01-01 --period-end 2025-01-31       --opening 1000.00 --closing 1050.00       --csv bank.csv
```
