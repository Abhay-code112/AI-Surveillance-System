FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HUGGINGFACE_HUB_CACHE=/home/appuser/.cache/huggingface

WORKDIR /app

# Create a non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /home/appuser -s /sbin/nologin -c "Docker image user" appuser

# Install system dependencies required for OpenCV and ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories and set permissions before switching to non-root user
RUN mkdir -p /app/backend /app/data \
    /app/storage/uploads \
    /app/storage/screenshots \
    /app/storage/clips \
    /home/appuser/.cache/huggingface \
    && chown -R appuser:appgroup /app /home/appuser

# Switch to non-root user
USER appuser

# Copy requirements and install
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Add pip bin to PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy the backend code
COPY --chown=appuser:appgroup . /app/backend

# Add meaningful healthcheck checking database and API via the new /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
