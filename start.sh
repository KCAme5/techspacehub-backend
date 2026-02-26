#!/bin/bash
# Start Celery worker in background
celery -A cybercraft worker --loglevel=info &

# Start Daphne (ASGI) - supports both HTTP and WebSockets
daphne -b 0.0.0.0 -p 8000 cybercraft.asgi:application