#!/usr/bin/env python
"""
Fix database schema issues for Coolify deployment.
This command fixes missing primary key constraints that cause migration failures.
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Fix database schema issues (missing PK constraints)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Checking database schema...'))
        
        with connection.cursor() as cursor:
            # Check if accounts_user table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'accounts_user'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                self.stdout.write(self.style.WARNING('accounts_user table does not exist yet. Skipping.'))
                return
            
            # Check for primary key constraint
            cursor.execute("""
                SELECT COUNT(*) FROM pg_constraint 
                WHERE conrelid = 'accounts_user'::regclass 
                AND contype = 'p';
            """)
            has_pk = cursor.fetchone()[0] > 0
            
            if has_pk:
                self.stdout.write(self.style.SUCCESS('accounts_user has primary key constraint. OK.'))
            else:
                self.stdout.write(self.style.ERROR('accounts_user MISSING primary key constraint!'))
                self.stdout.write(self.style.NOTICE('Attempting to fix...'))
                
                try:
                    with transaction.atomic():
                        # Check if id column exists and is unique
                        cursor.execute("""
                            SELECT COUNT(*) FROM pg_indexes 
                            WHERE tablename = 'accounts_user' 
                            AND indexname LIKE '%id%'
                            AND indexdef LIKE '%UNIQUE%';
                        """)
                        has_unique_index = cursor.fetchone()[0] > 0
                        
                        if has_unique_index:
                            self.stdout.write(self.style.NOTICE('Found unique index on id, dropping it first...'))
                            cursor.execute("""
                                DO $$
                                DECLARE
                                    idx_name text;
                                BEGIN
                                    SELECT indexname INTO idx_name FROM pg_indexes 
                                    WHERE tablename = 'accounts_user' 
                                    AND indexname LIKE '%id%' 
                                    AND indexdef LIKE '%UNIQUE%';
                                    IF idx_name IS NOT NULL THEN
                                        EXECUTE 'DROP INDEX ' || idx_name;
                                    END IF;
                                END $$;
                            """)
                        
                        # Add primary key constraint
                        cursor.execute("""
                            ALTER TABLE accounts_user 
                            ADD CONSTRAINT accounts_user_pkey PRIMARY KEY (id);
                        """)
                        self.stdout.write(self.style.SUCCESS('Fixed: Added primary key constraint!'))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Could not fix: {e}'))
                    self.stdout.write(self.style.WARNING(
                        'Manual fix required. Connect to your database and run:\n'
                        '  ALTER TABLE accounts_user ADD CONSTRAINT accounts_user_pkey PRIMARY KEY (id);'
                    ))
            
            # Also check other tables that reference accounts_user
            tables_to_check = [
                'accounts_activitylog',
                'accounts_loginattempt',
                'accounts_profile',
                'accounts_subscription',
                'accounts_wallet',
                'accounts_referral',
                'accounts_withdrawalrequest',
            ]
            
            for table in tables_to_check:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, [table])
                if cursor.fetchone()[0]:
                    cursor.execute("""
                        SELECT COUNT(*) FROM pg_constraint 
                        WHERE conrelid = %s::regclass 
                        AND contype = 'p';
                    """, [table])
                    if cursor.fetchone()[0] > 0:
                        self.stdout.write(self.style.SUCCESS(f'{table} has primary key. OK.'))
                    else:
                        self.stdout.write(self.style.WARNING(f'{table} missing primary key!'))
