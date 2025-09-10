## Import OFX/QFX
```bash
uv run ledger-dev import-ofx       --account-id 1       --period-start 2025-01-01 --period-end 2025-01-31       --opening 1000.00 --closing 1050.00       --ofx bank.ofx
```
Notes:
- Dedupes by `FITID` when available, else by `(date, amount, description)`.
- Supports typical SGML-style OFX/QFX where tags may not be closed.
- Combines `<NAME>` and `<MEMO>` for description if both present.
