FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install uv
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./

# Use uv to install dependencies from lockfile
RUN uv sync --frozen

COPY main.py ./
COPY mcp4immich ./mcp4immich
COPY docs ./docs

ENV MCP4IMMICH_SPEC_CACHE=/app/.cache/openapi

CMD ["uv", "run", "python", "main.py"]
