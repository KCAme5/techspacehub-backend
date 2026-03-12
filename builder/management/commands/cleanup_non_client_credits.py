"""
cleanup_non_client_credits.py - Django management command to remove credits from non-client users
Run: python manage.py cleanup_non_client_credits [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from builder.models import UserCredits


class Command(BaseCommand):
    help = 'Remove credits from users who are not clients (students, staff, management)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        dry_run = options['dry_run']
        
        # Get users who have credits but are NOT clients
        non_client_users_with_credits = User.objects.filter(
            ai_credits__isnull=False,
        ).exclude(role='client')
        
        if dry_run:
            self.stdout.write(f"[DRY RUN] Would remove credits from {non_client_users_with_credits.count()} non-client users:")
            for user in non_client_users_with_credits:
                self.stdout.write(f"  - {user.username} ({user.email}) - Role: {user.role}")
            return
        
        removed_count = 0
        
        with transaction.atomic():
            for user in non_client_users_with_credits:
                try:
                    credits_record = user.ai_credits
                    credits_record.delete()
                    removed_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Removed credits from {user.username} (role: {user.role})')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to remove credits from {user.username}: {e}')
                    )
        
        self.stdout.write(
            self.style.WARNING(
                f'\nCompleted! Removed credits from {removed_count} non-client users.'
            )
        )
