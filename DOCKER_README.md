## Docker usage

### Build the image
```bash
docker build -t journaled:dev -f Dockerfile .
```

### Run with SQLite (no DB container)
```bash
docker run --rm -it -v $(pwd)/journaled:/app/journaled journaled:dev journaled-dev init-db
docker run --rm -it -v $(pwd)/journaled:/app/journaled journaled:dev journaled-dev seed-coa
```

### Run with Postgres (docker compose)
```bash
docker compose up -d --build
# Exec into app and use CLI
docker compose exec app journaled-dev init-db
docker compose exec app journaled-dev seed-coa
```

Notes:
- Image uses **uv** in both build and runtime stages per your preference.
- The runtime defaults to SQLite if `DATABASE_URL` is not set.
- Swap `tail -f /dev/null` with your future server command (e.g., `uv run uvicorn ...`) once we add an API.
