import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybercraft.settings')
django.setup()

def get_columns(table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
        return [row[0] for row in cursor.fetchall()]

def get_constraints(table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT conname, contype
            FROM pg_catalog.pg_constraint
            WHERE conrelid = '{table_name}'::regclass
        """)
        return cursor.fetchall()

if __name__ == "__main__":
    table = 'courses_lesson'
    try:
        print(f"=== {table} ===")
        constraints = get_constraints(table)
        print("Constraints:")
        for con in constraints:
            ctype_map = {
                'p': 'Primary Key',
                'u': 'Unique',
                'f': 'Foreign Key',
                'c': 'Check',
                't': 'Trigger',
                'x': 'Exclusion'
            }
            ctype = ctype_map.get(con[1], con[1])
            print(f"  - {con[0]} ({ctype})")
    except Exception as e:
        print(f"Error: {e}")
