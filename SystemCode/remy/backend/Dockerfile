# uv resolves the workspace, so the build context is SystemCode/.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

# Every workspace member's pyproject is needed to read uv.lock, so copy them
# all first and let Docker cache the dependency install.
COPY pyproject.toml uv.lock ./
COPY remy/api/pyproject.toml remy/api/pyproject.toml
COPY remy/backend/pyproject.toml remy/backend/pyproject.toml
COPY remy/workflows/pyproject.toml remy/workflows/pyproject.toml
COPY remy/domain/pyproject.toml remy/domain/pyproject.toml
COPY remy/data-crawler/pyproject.toml remy/data-crawler/pyproject.toml
COPY remy/data-preparation/pyproject.toml remy/data-preparation/pyproject.toml
RUN uv sync --frozen --no-dev --package remy-backend --no-install-workspace

COPY remy/backend remy/backend
RUN uv sync --frozen --no-dev --package remy-backend

EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-dev", "--package", "remy-backend", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
