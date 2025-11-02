#!/usr/bin/env bash
set -e

# Simple DB wait loop (Postgres)
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database to be ready..."
  # Parse host and port from DATABASE_URL or default to db:5432
  DB_HOST=${DB_HOST:-$(echo $DATABASE_URL | sed -n 's#.*@\\([^:/]*\\).*#\\1#p')}
  DB_PORT=${DB_PORT:-5432}
else
  DB_HOST=${DB_HOST:-db}
  DB_PORT=${DB_PORT:-5432}
fi

# Wait for Postgres
attempts=0
until nc -z -v -w5 "$DB_HOST" "$DB_PORT"; do
  attempts=$((attempts+1))
  echo "Waiting for Postgres at $DB_HOST:$DB_PORT (attempt $attempts)..."
  sleep 2
  if [ $attempts -ge 30 ]; then
    echo "Postgres did not become available in time, exiting."
    exit 1
  fi
done

echo "Postgres is up - continuing"

# Run migrations and collectstatic
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Create a default superuser if environment variables are provided (optional)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
  python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); \
  username='$DJANGO_SUPERUSER_USERNAME'; \
  email='$DJANGO_SUPERUSER_EMAIL'; \
  password='$DJANGO_SUPERUSER_PASSWORD'; \
  u, created = User.objects.get_or_create(username=username, defaults={'email': email}); \
  u.set_password(password); u.is_staff=True; u.is_superuser=True; u.save()"
fi

# Execute the CMD from Dockerfile (gunicorn)
exec "$@"
