from .models import Enrollment


def filter_week_content_by_plan(week_data, plan, enrollment):
    """
    Filters week content based on user's enrollment plan
    - FREE: only first 2 lessons unlocked, project and quiz locked
    - BASIC/PRO: all content unlocked
    """
    plan = plan.upper() if plan else "FREE"

    if plan == "FREE":
        # Filter lessons - only first 2 are accessible
        if "lessons" in week_data:
            for i, lesson in enumerate(week_data["lessons"]):
                if i < 2:
                    lesson["is_locked"] = False
                else:
                    lesson["is_locked"] = True

        # Lock project and quiz for free users
        if "project" in week_data and week_data["project"]:
            week_data["project"]["is_locked"] = True

        if "quiz" in week_data and week_data["quiz"]:
            week_data["quiz"]["is_locked"] = True

    else:
        # Paid users - unlock everything
        if "lessons" in week_data:
            for lesson in week_data["lessons"]:
                lesson["is_locked"] = False

        if "project" in week_data and week_data["project"]:
            week_data["project"]["is_locked"] = False

        if "quiz" in week_data and week_data["quiz"]:
            week_data["quiz"]["is_locked"] = False

    return week_data


def check_lesson_access(lesson, user):
    """
    Check if user has access to a specific lesson
    """
    try:
        enrollment = Enrollment.objects.get(user=user, week=lesson.week, is_active=True)

        if enrollment.plan == "FREE":
            # Free users can only access first 2 lessons
            first_two_lessons = lesson.week.lessons.order_by("order")[:2]
            return lesson in first_two_lessons
        else:
            # Paid users can access all lessons
            return True
    except Enrollment.DoesNotExist:
        return False
