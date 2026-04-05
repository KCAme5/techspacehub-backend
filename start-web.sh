#!/bin/bash
set -e

# ========== STARTUP SCRIPT FOR DAPHNE (ASGI) ==========
# This runs on Render or any Docker container

PORT=${PORT:-10000}

echo "[$(date)] ========== DJANGO STARTUP =========="
echo "[$(date)] Running Django migrations..."

# Try normal migration first, if it fails (tables exist), fake the ones that exist
python manage.py migrate --noinput 2>/dev/null || {
    echo "[$(date)] Some migrations already exist, marking as applied..."
    python manage.py migrate --fake-all --noinput
}

echo "[$(date)] Collecting static files..."
python manage.py collectstatic --noinput

echo "[$(date)] ========== STARTING DAPHNE =========="
echo "[$(date)] Starting Daphne ASGI server on port ${PORT}..."
echo "[$(date)] Daphne will handle HTTP + WebSocket connections"

# Start Daphne and bind to the correct port
daphne \
    -b 0.0.0.0 \
    -p ${PORT} \
    --ws-per-message-deflate \
    --application-close-timeout 5 \
    --ping-interval 20 \
    --ping-timeout 20 \
    cybercraft.asgi:application

echo "[$(date)] Daphne stopped"
