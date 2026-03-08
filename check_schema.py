import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybercraft.settings')
django.setup()

def check_pk_unique(table_name):
    print(f"--- Checking {table_name} ---")
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                a.attname AS column_name,
                i.indisprimary AS is_primary,
                i.indisunique AS is_unique
            FROM
                pg_index i
            JOIN
                pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE
                i.indrelid = '{table_name}'::regclass
        """)
        rows = cursor.fetchall()
        if not rows:
            print("No indexes found (no PK or unique constraints).")
        for row in rows:
            print(f"Col: {row[0]}, PK: {row[1]}, Unique: {row[2]}")

if __name__ == "__main__":
    try:
        check_pk_unique('courses_lesson')
        check_pk_unique('courses_course')
        check_pk_unique('courses_week')
    except Exception as e:
        print(f"Error: {e}")
