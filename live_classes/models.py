# live_classes/models.py
"""
Models for scheduling and managing live classes (Jitsi-based) and their recordings.

Key models:
- LiveClass: a scheduled live session tied to a Course (and instructor).
- LiveClassRecording: stores metadata/URL for a recorded session.
- LiveClassAttendance: track which users attended or were invited.
"""

'''from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

User = settings.AUTH_USER_MODEL


class LiveClass(models.Model):
    REPEAT_CHOICES = [
        ("none", "Does not repeat"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    VISIBILITY_CHOICES = [
        ("public", "Public"),  # Everyone can view (if you expose listing)
        ("enrolled", "Enrolled"),  # Only users enrolled in the course
        ("pro", "Pro only"),  # Only Pro-tier subscribers / special access
        ("private", "Private"),  # Invite-only (via attendance/invite list)
    ]

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="live_classes",
        help_text="Course that this live class belongs to",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructed_live_classes",
        help_text="User who will host/teach the live class",
    )

    # Scheduling
    start_time = models.DateTimeField(help_text="Start time (UTC recommended)")
    end_time = models.DateTimeField(help_text="End time (UTC recommended)")
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="Timezone string for display (e.g. Africa/Nairobi)",
    )
    repeat = models.CharField(max_length=16, choices=REPEAT_CHOICES, default="none")
    repeat_count = models.PositiveIntegerField(
        default=0,
        help_text="If repeating, how many occurrences (0 = infinite / until manually stopped)",
    )

    # Jitsi integration fields
    jitsi_room_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier for Jitsi room (if empty, generated when class is created)",
    )
    jitsi_meet_url = models.URLField(
        blank=True, help_text="Full URL for joining the Jitsi meeting"
    )
    jitsi_password = models.CharField(
        max_length=128, blank=True, help_text="Optional meeting password"
    )

    # Recording & post-class
    allow_recording = models.BooleanField(default=True)
    recording_available = models.BooleanField(default=False)

    # Access control
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default="enrolled"
    )
    capacity = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="0 = unlimited; otherwise maximum attendees",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["start_time"]),
            models.Index(fields=["course"]),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title} ({self.start_time.isoformat()})"

    # --- Helper properties ---
    @property
    def is_upcoming(self):
        return (not self.is_cancelled) and (self.start_time > timezone.now())

    @property
    def is_live(self):
        now = timezone.now()
        return (not self.is_cancelled) and (self.start_time <= now <= self.end_time)

    @property
    def is_past(self):
        return self.end_time < timezone.now()

    def seats_left(self):
        if self.capacity == 0:
            return None
        current = self.attendances.filter(status__in=("attending", "joined")).count()
        return max(0, self.capacity - current)

    def can_user_join(self, user):
        """Simple access check — call from your views/permissions for more advanced logic"""
        if self.is_cancelled:
            return False
        if self.visibility == "public":
            return True
        # Enrolled -> user must be enrolled in course
        if self.visibility == "enrolled":
            return user.enrollments.filter(course=self.course, is_active=True).exists()
        if self.visibility == "pro":
            # Expect a Subscription model with plan attribute; adapt if needed
            sub = getattr(user, "subscription", None)
            # Try common patterns:
            try:
                user_sub = user.subscription  # if OneToOne
            except Exception:
                user_sub = None
            if not user_sub:
                # fallback: query Subscription model if exists
                try:
                    from accounts.models import Subscription as SubModel

                    user_sub = SubModel.objects.filter(
                        user=user, is_active=True
                    ).first()
                except Exception:
                    user_sub = None
            if user_sub and getattr(user_sub, "plan", "").lower() in ("pro", "premium"):
                return True
            return False
        if self.visibility == "private":
            return self.attendances.filter(
                user=user, status__in=("invited", "attending", "joined")
            ).exists()
        return False

    def ensure_jitsi(self, base_url=None, force=False):
        """
        Ensure Jitsi room name and join URL exist.
        base_url: optional base URL for Jitsi (e.g. https://meet.jit.si)
        If empty, just generate a room name. Returns (room_name, meet_url)
        """
        if self.jitsi_room_name and not force:
            room = self.jitsi_room_name
        else:
            # deterministic name: course-<id>-class-<id>-timestamp
            ts = int(self.start_time.timestamp())
            room = f"course-{self.course.id}-class-{self.id or 'temp'}-{ts}"
            # keep it URL-safe
            room = room.replace(" ", "-").lower()
            self.jitsi_room_name = room
            if base_url:
                self.jitsi_meet_url = f"{base_url.rstrip('/')}/{room}"
            else:
                # default to public meet.jit.si pattern (you may host your own)
                self.jitsi_meet_url = f"https://meet.jit.si/{room}"
            # Note: do NOT save here automatically — caller may want to set password etc.
        return self.jitsi_room_name, self.jitsi_meet_url


class LiveClassRecording(models.Model):
    """Stores recordings (or links) for a completed live class."""

    live_class = models.ForeignKey(
        LiveClass, on_delete=models.CASCADE, related_name="recordings"
    )
    title = models.CharField(max_length=255, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    file_url = models.URLField(
        blank=True, help_text="URL to the recording (S3, Vimeo, external)"
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        display = self.title or f"Recording for {self.live_class.title}"
        return f"{display} ({self.recorded_at.date().isoformat()})"


class LiveClassAttendance(models.Model):
    """
    Tracks invite/attendance for users.
    status: invited / attending / joined / left / no_show
    """

    STATUS_CHOICES = [
        ("invited", "Invited"),
        ("attending", "Attending"),
        ("joined", "Joined"),
        ("left", "Left"),
        ("no_show", "No show"),
    ]

    live_class = models.ForeignKey(
        LiveClass, on_delete=models.CASCADE, related_name="attendances"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="live_attendances"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="invited")
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_attendances",
    )

    class Meta:
        unique_together = ["live_class", "user"]
        ordering = ["-joined_at", "user__username"]

    def __str__(self):
        return f"{self.user} - {self.live_class.title} ({self.status})"
'''
