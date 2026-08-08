# ---- builder ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- runtime ----
FROM python:3.12-slim-bookworm
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app \
    && mkdir -p /data && chown app:app /data
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/line-connect.db
VOLUME ["/data"]
USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["uvicorn", "line_connect.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", \
     "--timeout-graceful-shutdown", "35", \
     "--no-access-log"]
