# syntax=docker/dockerfile:1.7

############################
# Builder / Dev stage (uv) #
############################
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm AS builder

WORKDIR /app/journaled

# Copy only dependency manifests first for better caching
COPY pyproject.toml ./
# If you generate a lock file later, uncomment the next line to improve reproducible builds
# COPY uv.lock ./

# Preload dependencies into .venv without project code
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --group dev

# Now copy the project source
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Install project into the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group dev

############################
# Runtime stage (uv image) #
############################
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm AS runtime

WORKDIR /app/journaled
COPY pyproject.toml ./
COPY src/ ./src/ 
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Copy the prepared venv and source
COPY --from=builder /app/journaled/.venv ./.venv
COPY --from=builder /app/journaled/src ./src
COPY --from=builder /app/journaled/alembic ./alembic
COPY --from=builder /app/journaled/alembic.ini ./alembic.ini
COPY --from=builder /app/journaled/pyproject.toml ./pyproject.toml

# Default environment: use SQLite unless DATABASE_URL provided
ENV DATABASE_URL="sqlite:///./dev.db"
ENV PATH="/app/journaled/.venv/bin:${PATH}"

# Healthcheck script (simple) to ensure Python can import the package
RUN python -c "import sys; print(sys.version)"

# Default command: show help
CMD ["journaled-dev"]
