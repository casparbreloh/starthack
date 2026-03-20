FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies only (no dev group = no torch)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-dev

# Copy source and trained model artifacts
COPY . .
RUN uv sync --no-dev

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["lambda_handler.handler"]
