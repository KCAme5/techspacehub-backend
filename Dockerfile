FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Finalize permissions for entrypoint
RUN chmod +x /app/entrypoint.sh

USER appuser

# Run collectstatic during build
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]

# Start command
CMD ["gunicorn", "cybercraft.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "3", "--timeout", "120"]