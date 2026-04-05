FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-traditional \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Make startup scripts executable
RUN chmod +x /app/start-web.sh /app/start-celery.sh

# Collect static files
RUN python manage.py collectstatic --noinput

USER appuser

# Render uses port 10000, HF Spaces uses 7860
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-10000}/api/accounts/health/')" || exit 1

# Default to web server (can override with startCommand in render.yaml)
CMD ["/app/start-web.sh"]