#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec gunicorn cybercraft.wsgi:application \
    --bind 0.0.0.0:7860 \
    --workers 3 \
    --timeout 120 \
    --preload