# progress/models.py
from django.db import models
from django.conf import settings


class UserLessonProgress(models.Model):
    """Tracks learner progress at the lesson level for hub education path."""
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lesson       = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE)
    completed    = models.BooleanField(default=False)
    drills_done  = models.IntegerField(default=0)
    quiz_passed  = models.BooleanField(default=False)
    xp_awarded   = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'lesson']
        verbose_name = 'Lesson Progress'
        verbose_name_plural = 'Lesson Progress Records'

    def __str__(self):
        status = '✓' if self.completed else '…'
        return f"[{status}] {self.user.username} — {self.lesson.title}"


class UserModuleAccess(models.Model):
    """Records that a user has paid for (or has free access to) a module."""
    ACCESS_CHOICES = [
        ('single',     'Single Module'),
        ('full_level', 'Full Level'),
    ]
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    module      = models.ForeignKey('courses.Module', on_delete=models.CASCADE)
    access_type = models.CharField(max_length=20, choices=ACCESS_CHOICES)
    granted_at  = models.DateTimeField(auto_now_add=True)
    payment     = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        unique_together = ['user', 'module']
        verbose_name = 'Module Access'
        verbose_name_plural = 'Module Access Records'

    def __str__(self):
        return f"{self.user.username} → {self.module.title} ({self.access_type})"
