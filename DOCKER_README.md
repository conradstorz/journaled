## Docker usage

### Build the image
```bash
docker build -t ledger:dev -f Dockerfile .
```

### Run with SQLite (no DB container)
```bash
docker run --rm -it -v $(pwd)/ledger:/app/ledger ledger:dev ledger-dev init-db
docker run --rm -it -v $(pwd)/ledger:/app/ledger ledger:dev ledger-dev seed-coa
```

### Run with Postgres (docker compose)
```bash
docker compose up -d --build
# Exec into app and use CLI
docker compose exec app ledger-dev init-db
docker compose exec app ledger-dev seed-coa
```

Notes:
- Image uses **uv** in both build and runtime stages per your preference.
- The runtime defaults to SQLite if `DATABASE_URL` is not set.
- Swap `tail -f /dev/null` with your future server command (e.g., `uv run uvicorn ...`) once we add an API.
