#!/bin/bash
set -e

# ========== STARTUP SCRIPT FOR CELERY WORKER ==========
# This runs on Render background worker

echo "[$(date)] ========== CELERY WORKER STARTUP =========="
echo "[$(date)] Starting Celery worker..."
echo "[$(date)] Broker: \${CELERY_BROKER_URL} (from Upstash)"
echo "[$(date)] Results: django-db (stored in Supabase)"

celery -A cybercraft worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10 \
    --time-limit=300 \
    --soft-time-limit=240 \
    --prefetch-multiplier=1

echo "[$(date)] Celery worker stopped"
