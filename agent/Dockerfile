FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=us-west-2 \
    AWS_DEFAULT_REGION=us-west-2

COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

CMD ["uv", "run", "mars-agent", "--no-memory"]
