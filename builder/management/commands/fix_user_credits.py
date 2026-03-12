"""
fix_user_credits.py - Django management command to fix credits for a specific CLIENT user
Run: python manage.py fix_user_credits <username>
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from builder.models import UserCredits


class Command(BaseCommand):
    help = "Fix credits for a specific CLIENT user by granting them 20 credits"

    def add_arguments(self, parser):
        parser.add_argument(
            "username", type=str, help="Username of the CLIENT user to fix"
        )

    def handle(self, *args, **options):
        username = options["username"]
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Check if user is a client
        if user.role != "client":
            self.stdout.write(
                self.style.WARNING(
                    f'User "{username}" has role "{user.role}", not "client". No credits granted.'
                )
            )
            return

        credits_obj, created = UserCredits.objects.get_or_create(
            user=user,
            defaults={
                "credits": 20,
                "total_purchased": 0,
                "total_used": 0,
                "is_free_tier": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created credits record for CLIENT {username}: 20 credits"
                )
            )
        else:
            # Update existing record to ensure they have at least 20 credits
            if credits_obj.credits < 20:
                credits_obj.credits = 20
                credits_obj.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Updated CLIENT {username} credits to: 20")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"CLIENT {username} already has {credits_obj.credits} credits"
                    )
                )
