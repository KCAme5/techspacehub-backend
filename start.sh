#!/bin/bash
# Start Redis if not running (fallback)
redis-server --daemonize yes || true

# Start Celery worker in background
celery -A cybercraft worker --loglevel=info &

# Start Gunicorn
gunicorn cybercraft.wsgi:application --bind 0.0.0.0:8000