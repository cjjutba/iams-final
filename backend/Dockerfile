# IAMS Backend - Production Dockerfile
# Multi-stage build for smaller final image

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies for native packages (insightface, opencv, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies (OpenCV, image libs, FFmpeg for video pipeline, gosu for entrypoint)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    ffmpeg \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Create required directories with correct ownership
RUN mkdir -p data/faiss data/uploads/faces data/hls logs \
    && chown -R appuser:appuser /app

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8000

# Entrypoint fixes volume ownership then runs uvicorn as appuser
ENTRYPOINT ["/app/entrypoint.sh"]
