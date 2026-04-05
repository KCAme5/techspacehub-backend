#!/bin/bash
set -e

# ========== STARTUP SCRIPT FOR DAPHNE (ASGI) ==========
# This runs on Render or any Docker container

PORT=${PORT:-10000}

echo "[$(date)] ========== DJANGO STARTUP =========="
echo "[$(date)] Running Django migrations..."
python manage.py migrate --noinput

echo "[$(date)] Collecting static files..."
python manage.py collectstatic --noinput

echo "[$(date)] ========== STARTING DAPHNE =========="
echo "[$(date)] Starting Daphne ASGI server on port ${PORT}..."
echo "[$(date)] Daphne will handle HTTP + WebSocket connections"

daphne \
    -b 0.0.0.0 \
    -p ${PORT} \
    --ws-per-message-deflate \
    --application-close-timeout 5 \
    --ping-interval 20 \
    --ping-timeout 20 \
    cybercraft.asgi:application

echo "[$(date)] Daphne stopped"
