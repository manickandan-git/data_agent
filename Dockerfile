# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.13-slim-bookworm AS builder

COPY --from=uv /uv /bin/uv
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md MANIFEST.in ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runtime

RUN groupadd --gid 10001 dataagent \
    && useradd --uid 10001 --gid dataagent --create-home --shell /usr/sbin/nologin dataagent

WORKDIR /app

ENV APP_ENVIRONMENT=production \
    API_HOST=0.0.0.0 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder --chown=dataagent:dataagent /app/.venv /app/.venv
COPY --chown=dataagent:dataagent alembic.ini ./
COPY --chown=dataagent:dataagent migrations ./migrations
COPY --chown=dataagent:dataagent data ./data
RUN mkdir -p /app/data/extract /app/data/transform \
    && chown -R dataagent:dataagent /app/data

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).read()"]

CMD ["data-agent-api"]
