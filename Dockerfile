# Use Python 3.13 slim image for stability and smaller size
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic-dev \
    gcc \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy uv lock files and metadata required by build system
COPY pyproject.toml uv.lock README.md ./
COPY S-TOON-Protocol ./S-TOON-Protocol

# Restore S-TOON-Protocol git repository metadata
RUN mv ./S-TOON-Protocol/git_dir ./S-TOON-Protocol/.git

# Configure git to use the local clone offline
RUN git config --global url."/app/S-TOON-Protocol".insteadOf "https://github.com/azimuth-logic-research/S-TOON-Protocol.git"

# Install dependencies using uv sync --frozen
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY ./app ./app

# Install project
RUN uv sync --frozen --no-dev

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
