"""
grant_missing_credits.py - Django management command to grant 20 credits to CLIENT users who don't have any
Run: python manage.py grant_missing_credits
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from builder.models import UserCredits


class Command(BaseCommand):
    help = "Grant 20 credits to existing CLIENT users who do not have credit records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        dry_run = options["dry_run"]

        # Get only CLIENT users who don't have credit records
        users_without_credits = User.objects.filter(
            ai_credits__isnull=True, role="client"  # Only target client users
        )

        if dry_run:
            self.stdout.write(
                f"[DRY RUN] Would grant credits to {users_without_credits.count()} CLIENT users:"
            )
            for user in users_without_credits:
                self.stdout.write(
                    f"  - {user.username} ({user.email}) - Role: {user.role}"
                )
            return

        created_count = 0

        with transaction.atomic():
            for user in users_without_credits:
                UserCredits.objects.create(
                    user=user,
                    credits=20,
                    total_purchased=0,
                    total_used=0,
                    is_free_tier=True,
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Granted 20 credits to CLIENT: {user.username} (role: {user.role})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Granted credits to {created_count} CLIENT users."
            )
        )
