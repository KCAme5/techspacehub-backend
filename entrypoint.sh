#!/usr/bin/env bash
set -e

echo "Starting CyberCraft..."

# Simple migration check
python manage.py migrate --noinput || echo "Migration failed but continuing..."
python manage.py collectstatic --noinput || echo "Static collection failed but continuing..."

exec "$@"
