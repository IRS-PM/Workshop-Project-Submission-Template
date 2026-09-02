FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml uv.lock ./
COPY remy/api/pyproject.toml remy/api/pyproject.toml
COPY remy/workflows/pyproject.toml remy/workflows/pyproject.toml
COPY remy/data-crawler/pyproject.toml remy/data-crawler/pyproject.toml
COPY remy/data-preparation/pyproject.toml remy/data-preparation/pyproject.toml
RUN uv sync --frozen --no-dev --package remy-data-preparation --no-install-workspace

COPY remy/data-preparation remy/data-preparation
RUN uv sync --frozen --no-dev --package remy-data-preparation

CMD ["uv", "run", "--frozen", "--no-dev", "--package", "remy-data-preparation", "dbt", "build", "--project-dir", "remy/data-preparation"]
