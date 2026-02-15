#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput

python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='adrianchan@cybercraft.com').exists():
    User.objects.create_superuser('AdrianKisa', 'adrianchan@cybercraft.com', 'youngTalentpassword123')
    print('Superuser created successfully!')
" || echo "Superuser creation skipped or failed."