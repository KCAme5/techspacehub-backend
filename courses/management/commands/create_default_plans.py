# courses/management/commands/create_default_plans.py
from django.core.management.base import BaseCommand
from courses.models import Plan, Week, WeekPlan


class Command(BaseCommand):
    help = "Create default free and premium plans"

    def handle(self, *args, **options):
        # Create Free Plan
        free_plan, created = Plan.objects.get_or_create(
            name="Free Trial",
            plan_type="free",
            defaults={
                "price": 0.00,
                "description": "Access first 2 lessons of each week for free",
                "features": ["First 2 lessons per week", "Community support"],
                "free_lessons_limit": 2,
                "includes_quizzes": False,
                "includes_projects": False,
                "includes_support": False,
            },
        )

        # Create Premium Plan
        premium_plan, created = Plan.objects.get_or_create(
            name="Premium Weekly",
            plan_type="premium",
            defaults={
                "price": 19.99,
                "description": "Full access to all weekly content including quizzes and projects",
                "features": [
                    "All lessons unlocked",
                    "Weekly quizzes",
                    "Practice projects",
                    "Priority support",
                    "Certificate of completion",
                ],
                "free_lessons_limit": 999,  # Essentially unlimited
                "includes_quizzes": True,
                "includes_projects": True,
                "includes_support": True,
            },
        )

        # Assign default plans to all weeks
        weeks = Week.objects.filter(is_active=True)
        for week in weeks:
            # Free plan
            WeekPlan.objects.get_or_create(
                week=week, plan=free_plan, defaults={"is_default": True}
            )
            # Premium plan
            WeekPlan.objects.get_or_create(week=week, plan=premium_plan)

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully created default plans and assigned them to weeks!"
            )
        )
