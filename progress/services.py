# progress/services.py
"""
Server-side unlock logic for hub education-path levels.
Called whenever a learner requests the module/lesson state for a level.
"""
from courses.models import Module
from progress.models import UserLessonProgress, UserModuleAccess


def get_level_progress_state(user, level):
    """
    Returns the full unlock state for all modules + lessons in a level.

    FREE RULE:    module.order <= 2  → always accessible
    PAID RULE:    module.order >= 3  → requires UserModuleAccess record
    LESSON RULE:  only first lesson open by default; each subsequent
                  lesson unlocks only when previous is complete
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
        has_paid       = module.id in paid_ids or has_full_level_access
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
            is_open = module_open and prev_lesson_done

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
