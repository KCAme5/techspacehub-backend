#!/usr/bin/env bash
set -e

echo "Starting CyberCraft..."

# Wait for database to be ready
echo "Waiting for database..."
for i in {1..30}; do
    python -c "import socket; socket.create_connection(('${DB_HOST:-db}', ${DB_PORT:-5432}), timeout=5)" 2>/dev/null && break
    echo "Database not ready, waiting... ($i/30)"
    sleep 2
done

# Check if migrations table exists and fix schema issues if needed
echo "Checking database schema..."
python manage.py fix_db_schema 2>/dev/null || echo "Schema check skipped (first run)"

# Run migrations with better error handling
echo "Running migrations..."
if python manage.py migrate --noinput; then
    echo "Migrations completed successfully"
else
    echo "WARNING: Migrations had issues, continuing anyway..."
    # List pending migrations
    python manage.py showmigrations --list 2>/dev/null || true
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || echo "Static collection skipped"

echo "Starting application..."
exec "$@"
