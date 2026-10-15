# syntax=docker/dockerfile:1.7

# --- Stockfish: официальный бинарник под архитектуру сборки (amd64 / arm64) ---
FROM debian:trixie-slim AS stockfish
ARG STOCKFISH_VERSION=sf_19
ARG TARGETARCH
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "$TARGETARCH" in \
      amd64) arch=x86-64 ;; \
      arm64) arch=arm64 ;; \
      *) echo "Неподдерживаемая архитектура: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/official-stockfish/Stockfish/releases/download/${STOCKFISH_VERSION}/stockfish-linux-${arch}-universal.tar.gz" \
      | tar xz -C /tmp; \
    install -m 0755 "/tmp/stockfish/stockfish-linux-${arch}-universal" /usr/local/bin/stockfish; \
    printf 'uci\nquit\n' | stockfish | grep -q '^uciok'

# --- База: Python + зависимости ---
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
COPY --from=stockfish /usr/local/bin/stockfish /usr/local/bin/stockfish
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    STOCKFISH_PATH=/usr/local/bin/stockfish
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./

# --- dev: + dev-зависимости, код монтируется volume'ом ---
FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
COPY . .
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]

# --- prod ---
FROM base AS prod
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY . .
RUN useradd --system --uid 1000 app
USER app
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
