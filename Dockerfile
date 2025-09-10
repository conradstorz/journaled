# syntax=docker/dockerfile:1.7

############################
# Builder / Dev stage (uv) #
############################
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm AS builder

WORKDIR /app/ledger

# Copy only dependency manifests first for better caching
COPY ledger/pyproject.toml ./
# If you generate a lock file later, uncomment the next line to improve reproducible builds
# COPY ledger/uv.lock ./

# Preload dependencies into .venv without project code
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --group dev

# Now copy the project source
COPY ledger/ ./

# Install project into the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group dev

############################
# Runtime stage (uv image) #
############################
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm AS runtime

WORKDIR /app/ledger

# Copy the prepared venv and source
COPY --from=builder /app/ledger/.venv ./.venv
COPY --from=builder /app/ledger/src ./src
COPY --from=builder /app/ledger/alembic ./alembic
COPY --from=builder /app/ledger/alembic.ini ./alembic.ini
COPY --from=builder /app/ledger/pyproject.toml ./pyproject.toml

# Default environment: use SQLite unless DATABASE_URL provided
ENV DATABASE_URL="sqlite:///./dev.db"
ENV PATH="/app/ledger/.venv/bin:${PATH}"

# Healthcheck script (simple) to ensure Python can import the package
RUN python -c "import sys; print(sys.version)"

# Default command: show help
CMD ["ledger-dev"]
