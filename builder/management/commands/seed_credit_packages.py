"""
seed_credit_packages.py - Django management command to populate credit packages.
Run: python manage.py seed_credit_packages
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from builder.models import CreditPackage
import uuid


class Command(BaseCommand):
    help = 'Seed the database with default credit packages'

    def handle(self, *args, **options):
        packages_data = [
            {
                'id': uuid.UUID('11111111-1111-1111-1111-111111111111'),
                'name': 'STARTER',
                'credits': 20,
                'price_kes': 300.00,
                'is_popular': False,
                'is_active': True,
                'sort_order': 1,
            },
            {
                'id': uuid.UUID('22222222-2222-2222-2222-222222222222'),
                'name': 'PRO',
                'credits': 60,
                'price_kes': 700.00,
                'is_popular': True,
                'is_active': True,
                'sort_order': 2,
            },
            {
                'id': uuid.UUID('33333333-3333-3333-3333-333333333333'),
                'name': 'POWER',
                'credits': 150,
                'price_kes': 1500.00,
                'is_popular': False,
                'is_active': True,
                'sort_order': 3,
            },
        ]

        created = 0
        updated = 0

        with transaction.atomic():
            for package_data in packages_data:
                package, created_new = CreditPackage.objects.update_or_create(
                    id=package_data['id'],
                    defaults=package_data
                )
                
                if created_new:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created package: {package.name}')
                    )
                else:
                    updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated package: {package.name}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCredit packages seeded successfully!\n'
                f'Created: {created} packages\n'
                f'Updated: {updated} packages\n'
                f'Total packages: {CreditPackage.objects.count()}'
            )
        )
