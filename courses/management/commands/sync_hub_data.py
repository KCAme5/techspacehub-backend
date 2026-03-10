from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import Course, Level, Module, Lesson, Week
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Migrates legacy Week data to the new Level -> Module hierarchy'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Hub data migration...'))
        
        with transaction.atomic():
            # 1. Handle Course 14 (C++) "Noob" cleanup
            course_14 = Course.objects.filter(pk=14).first()
            if course_14:
                noob_level = Level.objects.filter(course=course_14, slug='noob').first()
                if noob_level:
                    self.stdout.write(f"Cleaning up 'noob' level for course 14...")
                    # Link any modules or lessons away first if necessary, but we'll re-sync anyway
                    noob_level.delete()

            # 2. Iterate through all courses
            courses = Course.objects.all()
            total_migrated_lessons = 0
            
            for course in courses:
                weeks = Week.objects.filter(course=course).order_by('order', 'week_number')
                if not weeks.exists():
                    continue
                
                self.stdout.write(f"Processing Course: {course.title} (ID: {course.id})")
                
                for week in weeks:
                    # Determine level name and type
                    # Legacy level field in Week is a string: 'beginner', 'intermediate', 'advanced'
                    level_key = week.level.lower()
                    level_name = level_key.capitalize()
                    
                    # Get or Create the Level
                    level, created = Level.objects.get_or_create(
                        course=course,
                        level_type=level_key,
                        defaults={
                            'name': level_name,
                            'slug': slugify(level_name),
                            'description': f'This is the {level_name} level for {course.title}.',
                            'order': 1 if level_key == 'beginner' else (2 if level_key == 'intermediate' else 3),
                            'is_published': True
                        }
                    )
                    
                    if created:
                        self.stdout.write(f"  Created Level: {level.name}")
                    
                    # Create the Module from the Week
                    # Check if module already exists to avoid duplicates
                    module = Module.objects.filter(level=level, title=week.title).first()
                    if not module:
                        module = Module.objects.create(
                            level=level,
                            title=week.title,
                            description=week.description,
                            order=week.week_number,
                            is_published=True,
                            xp_reward=50,
                            single_module_price=week.price if week.price > 0 else 299.00
                        )
                        self.stdout.write(f"    Created Module: {module.title}")
                    
                    # Link all lessons from this week to the new module
                    lessons = Lesson.objects.filter(week=week)
                    count = lessons.count()
                    if count > 0:
                        lessons.update(module=module)
                        total_migrated_lessons += count
                        self.stdout.write(f"      Migrated {count} lessons to module.")

        self.stdout.write(self.style.SUCCESS(f'Migration complete! Total lessons updated: {total_migrated_lessons}'))
