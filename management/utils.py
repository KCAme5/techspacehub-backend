from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from courses.models import (
    Course,
    Week,
    Enrollment,
    WeeklyQuizSubmission,
    ProjectSubmission,
)
from billing.models import Payment

User = get_user_model()


def get_dashboard_overview():
    """Get main dashboard statistics"""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # User stats
    total_users = User.objects.count()
    active_students = User.objects.filter(role="student", is_active=True).count()
    active_staff = User.objects.filter(role="staff", is_active=True).count()
    new_users_today = User.objects.filter(date_joined__date=today).count()
    new_users_month = User.objects.filter(date_joined__date__gte=month_start).count()

    # Revenue stats
    total_revenue = (
        Payment.objects.filter(status="success").aggregate(total=Sum("amount"))["total"]
        or 0
    )

    revenue_today = (
        Payment.objects.filter(status="success", created_at__date=today).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    revenue_month = (
        Payment.objects.filter(
            status="success", created_at__date__gte=month_start
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    # Calculate month-over-month growth
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_revenue = (
        Payment.objects.filter(
            status="success",
            created_at__date__gte=last_month_start,
            created_at__date__lt=month_start,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    revenue_growth = 0
    if last_month_revenue > 0:
        revenue_growth = (
            (revenue_month - last_month_revenue) / last_month_revenue
        ) * 100

    # Enrollment stats
    total_enrollments = Enrollment.objects.count()
    active_enrollments = Enrollment.objects.filter(is_active=True).count()
    enrollments_today = Enrollment.objects.filter(enrolled_at__date=today).count()

    # Course stats
    total_courses = Course.objects.filter(is_active=True).count()
    total_weeks = Week.objects.count()

    # Completion rate
    completed_enrollments = Enrollment.objects.filter(completed=True).count()
    completion_rate = 0
    if total_enrollments > 0:
        completion_rate = (completed_enrollments / total_enrollments) * 100

    # Payment stats
    pending_payments = Payment.objects.filter(status="pending").count()
    failed_payments = Payment.objects.filter(status="failed").count()

    return {
        "users": {
            "total": total_users,
            "active_students": active_students,
            "active_staff": active_staff,
            "new_today": new_users_today,
            "new_this_month": new_users_month,
        },
        "revenue": {
            "total": float(total_revenue),
            "today": float(revenue_today),
            "this_month": float(revenue_month),
            "growth_percentage": round(revenue_growth, 2),
        },
        "enrollments": {
            "total": total_enrollments,
            "active": active_enrollments,
            "today": enrollments_today,
        },
        "courses": {
            "total": total_courses,
            "total_weeks": total_weeks,
        },
        "metrics": {
            "completion_rate": round(completion_rate, 2),
            "pending_payments": pending_payments,
            "failed_payments": failed_payments,
        },
    }


def get_revenue_trend(days=30):
    """Get revenue trend for the last N days"""
    today = timezone.now().date()
    start_date = today - timedelta(days=days)

    revenue_by_day = (
        Payment.objects.filter(status="success", created_at__date__gte=start_date)
        .values("created_at__date")
        .annotate(revenue=Sum("amount"))
        .order_by("created_at__date")
    )

    # Format for frontend
    data = []
    for item in revenue_by_day:
        data.append(
            {
                "date": item["created_at__date"].strftime("%Y-%m-%d"),
                "revenue": float(item["revenue"]),
            }
        )

    return data


def get_enrollment_trend(days=30):
    """Get enrollment trend for the last N days"""
    today = timezone.now().date()
    start_date = today - timedelta(days=days)

    enrollments_by_day = (
        Enrollment.objects.filter(enrolled_at__date__gte=start_date)
        .values("enrolled_at__date")
        .annotate(count=Count("id"))
        .order_by("enrolled_at__date")
    )

    data = []
    for item in enrollments_by_day:
        data.append(
            {
                "date": item["enrolled_at__date"].strftime("%Y-%m-%d"),
                "enrollments": item["count"],
            }
        )

    return data


def get_course_distribution():
    """Get course enrollment distribution.
    Using Enrollment as the base query is more reliable for PostgreSQL grouping.
    """
    stats = (
        Enrollment.objects.filter(week__course__is_active=True)
        .values("week__course__title")
        .annotate(enrollment_count=Count("id"))
        .order_by("-enrollment_count")[:10]
    )

    data = []
    for item in stats:
        data.append({
            "name": item["week__course__title"], 
            "value": item["enrollment_count"]
        })

    # Fallback: if no enrollments, show top active courses with 0
    if not data:
        courses = Course.objects.filter(is_active=True)[:10]
        for course in courses:
            data.append({"name": course.title, "value": 0})

    return data


def get_recent_activity(limit=20):
    """Get recent platform activity"""
    activities = []

    # Recent enrollments
    recent_enrollments = Enrollment.objects.select_related(
        "user", "week__course"
    ).order_by("-enrolled_at")[:limit]

    for enrollment in recent_enrollments:
        activities.append(
            {
                "type": "enrollment",
                "user": enrollment.user.username,
                "action": f"Enrolled in {enrollment.week.course.title} - Week {enrollment.week.week_number}",
                "time": enrollment.enrolled_at,
            }
        )

    # Recent payments
    recent_payments = (
        Payment.objects.filter(status="success")
        .select_related("user", "week")
        .order_by("-created_at")[:limit]
    )

    for payment in recent_payments:
        activities.append(
            {
                "type": "payment",
                "user": payment.user.username,
                "action": f"Paid {payment.currency} {payment.amount} for {payment.week.title if payment.week else 'subscription'}",
                "time": payment.created_at,
            }
        )

    # Recent quiz submissions
    recent_quizzes = WeeklyQuizSubmission.objects.select_related(
        "student", "weekly_quiz__week"
    ).order_by("-submitted_at")[:limit]

    for quiz in recent_quizzes:
        activities.append(
            {
                "type": "quiz",
                "user": quiz.student.username,
                "action": f"Completed quiz with {quiz.score}% - Week {quiz.weekly_quiz.week.week_number}",
                "time": quiz.submitted_at,
            }
        )

    # Sort all activities by time
    activities.sort(key=lambda x: x["time"], reverse=True)

    return activities[:limit]
