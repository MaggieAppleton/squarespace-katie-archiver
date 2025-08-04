# Production Dockerfile for Squarespace Blog Archiver
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/
COPY archiver_config.json ./

# Create output directory
RUN mkdir -p /app/output
RUN mkdir -p /app/logs

# Set up non-root user for security
RUN groupadd -r archiver && useradd -r -g archiver archiver
RUN chown -R archiver:archiver /app
USER archiver

# Set environment variables
ENV PYTHONPATH=/app
ENV ARCHIVER_LOG_LEVEL=INFO
ENV ARCHIVER_OUTPUT_DIR=/app/output

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src.connectivity; print('OK')" || exit 1

# Default command
CMD ["python", "-m", "src.main", "archive", "--output", "/app/output"]