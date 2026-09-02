FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

# Copy dependency metadata first so Docker can cache dependency installation.
COPY pyproject.toml uv.lock ./
COPY remy/api/pyproject.toml remy/api/pyproject.toml
COPY remy/workflows/pyproject.toml remy/workflows/pyproject.toml
COPY remy/data-crawler/pyproject.toml remy/data-crawler/pyproject.toml
COPY remy/data-preparation/pyproject.toml remy/data-preparation/pyproject.toml
RUN uv sync --frozen --no-dev --package remy-api --no-install-workspace

COPY remy/api remy/api
COPY remy/workflows remy/workflows
RUN uv sync --frozen --no-dev --package remy-api

EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-dev", "--package", "remy-api", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
