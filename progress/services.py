# progress/services.py
"""
Server-side unlock logic for hub education-path levels.
Called whenever a learner requests the module/lesson state for a level.
"""
from courses.models import Module, Enrollment
from progress.models import UserLessonProgress, UserModuleAccess


def get_level_progress_state(user, level):
    """
    Returns the full unlock state for all modules + lessons in a level.

    FREE RULE:    module.order <= 2  → always accessible
    PAID RULE:    module.order >= 3  → requires UserModuleAccess record OR legacy Enrollment for a corresponding Week
    LESSON RULE:  all lessons in an open module are unlocked
    MODULE RULE:  next module unlocks only when all lessons in
                  current module are complete
    """
    modules = level.modules.prefetch_related('lessons').filter(is_published=True)

    paid_ids = set(
        UserModuleAccess.objects
        .filter(user=user, module__level=level)
        .values_list('module_id', flat=True)
    )
    has_full_level_access = UserModuleAccess.objects.filter(
        user=user, access_type='full_level', module__level=level
    ).exists()

    result = []
    prev_module_complete = True   # Gate: previous module must be complete

    for module in modules:
        is_free        = module.order <= 2
        
        # Check if any lesson in this module is part of a Week the user is enrolled in
        has_legacy_enrollment = False
        module_lesson_ids = module.lessons.values_list('id', flat=True)
        # We also check if the module title matches a week title or similar mapping
        # but the most robust way is to check if any week linked to this level's course
        # matches the content. Since 'Week' and 'Module' are almost 1:1 in this project structure:
        has_legacy_enrollment = Enrollment.objects.filter(
            user=user, 
            week__course=level.course,
            week__level=level.level_type,
            week__week_number=module.order, # Assuming order aligns with week_number
            is_active=True
        ).exists()

        has_paid       = module.id in paid_ids or has_full_level_access or has_legacy_enrollment
        is_accessible  = is_free or has_paid
        needs_payment  = not is_free and not has_paid
        module_open    = is_accessible and prev_module_complete

        lessons = module.lessons.filter(is_published=True).prefetch_related('drills', 'quiz')
        lesson_states = []
        prev_lesson_done     = True
        all_lessons_complete = True

        for lesson in lessons:
            prog    = UserLessonProgress.objects.filter(user=user, lesson=lesson).first()
            is_done = prog.completed if prog else False
            # If the module is open, ALL lessons in it are open as per user request
            is_open = module_open

            lesson_states.append({
                'id':        lesson.id,
                'title':     lesson.title,
                'icon':      lesson.icon,
                'order':     lesson.order,
                'xp_reward': lesson.xp_reward,
                'has_lab':   lesson.has_lab,
                'unlocked':  is_open,
                'completed': is_done,
                'drills_count': lesson.drills.count(),
                'quiz_count': 1 if hasattr(lesson, 'quiz') else 0,
            })

            if not is_done:
                all_lessons_complete = False
            prev_lesson_done = is_done

        result.append({
            'id':            module.id,
            'title':         module.title,
            'description':   module.description,
            'order':         module.order,
            'icon':          module.icon,
            'color':         module.color,
            'is_free':       is_free,
            'needs_payment': needs_payment,
            'module_open':   module_open,
            'all_complete':  all_lessons_complete,
            'single_price':  str(module.single_module_price),
            'lessons':       lesson_states,
        })

        prev_module_complete = all_lessons_complete

    return result
