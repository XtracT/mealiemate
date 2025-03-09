# Multi-stage build for MealieMate
# Stage 1: Build dependencies
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Build wheels
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels

# Install Python dependencies
RUN pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Create non-root user
RUN groupadd -g 1000 mealiemate && \
    useradd -u 1000 -g mealiemate -s /bin/bash -m mealiemate

# Copy application code
COPY --chown=mealiemate:mealiemate . .

# Create data directory with proper permissions
RUN mkdir -p /data && chown -R mealiemate:mealiemate /data
VOLUME /data

# Switch to non-root user
USER mealiemate

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import asyncio, sys; \
                 from services.mealie_api_service import MealieApiServiceImpl; \
                 service = MealieApiServiceImpl(); \
                 sys.exit(0 if asyncio.run(service.fetch_data('/api/app/about')) else 1)"

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Command to run the application
CMD ["python", "main.py"]

# Labels
LABEL org.opencontainers.image.title="MealieMate" \
      org.opencontainers.image.description="Meal planning and recipe management integration for Mealie" \
      org.opencontainers.image.source="https://github.com/yourusername/mealiemate" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.2.0"
