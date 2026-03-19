FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project

# Copy source
COPY . .
RUN uv sync

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
