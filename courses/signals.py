# courses/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WeeklyQuizSubmission, ProjectSubmission, WeeklyProgress


@receiver(post_save, sender=WeeklyQuizSubmission)
def update_weekly_progress_quiz(sender, instance, created, **kwargs):
    if created:
        try:
            weekly_progress = WeeklyProgress.objects.get(
                user=instance.student, week=instance.weekly_quiz.week
            )
            weekly_progress.quiz_completed = True
            weekly_progress.save()
        except WeeklyProgress.DoesNotExist:
            pass


@receiver(post_save, sender=ProjectSubmission)
def update_weekly_progress_project(sender, instance, created, **kwargs):
    if created:
        try:
            weekly_progress = WeeklyProgress.objects.get(
                user=instance.student, week=instance.weekly_project.week
            )
            weekly_progress.project_completed = True
            weekly_progress.save()
        except WeeklyProgress.DoesNotExist:
            pass
