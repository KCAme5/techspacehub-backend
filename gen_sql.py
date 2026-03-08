import os
import django
from django.core.management import call_command
from io import StringIO

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybercraft.settings')
django.setup()

out = StringIO()
try:
    call_command('sqlmigrate', 'courses', '0014', stdout=out)
    with open('migration_0014_fixed.sql', 'w', encoding='utf-8') as f:
        f.write(out.getvalue())
    print("SQL generated successfully in migration_0014_fixed.sql")
except Exception as e:
    print(f"Error: {e}")
