FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --no-dev --frozen

# Copy application code and personas
COPY api/ ./api/
COPY personas/ ./personas/

# Prevent uv from re-syncing on every run
ENV UV_NO_SYNC=1
ENV PERSONAS_DIR=./personas
ENV LOG_LEVEL=INFO

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
