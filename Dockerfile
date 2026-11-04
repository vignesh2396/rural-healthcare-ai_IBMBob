# Dockerfile — Rural Healthcare AI Navigation System
# =====================================================
# Multi-stage build for production deployment
# Base: Python 3.11 slim (smaller image)

FROM python:3.11-slim AS base

# Metadata
LABEL maintainer="Healthcare AI Team"
LABEL version="1.0.0"
LABEL description="Rural Healthcare AI Navigation System"

# Security: run as non-root user
RUN groupadd -r healthcare && useradd -r -g healthcare healthcare

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data rag/chroma_db && \
    chown -R healthcare:healthcare /app

# Switch to non-root user
USER healthcare

# Environment variables (non-secret defaults)
ENV APP_ENV=production
ENV LOG_LEVEL=INFO
ENV DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Expose Streamlit port
EXPOSE 8501

# Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Entry point
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
