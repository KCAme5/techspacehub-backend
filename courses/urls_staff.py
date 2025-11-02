from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_staff as views

router = DefaultRouter()
router.register(r"categories", views.StaffCategoryViewSet, basename="staff-category")
router.register(r"courses", views.StaffCourseViewSet, basename="staff-course")
router.register(r"weeks", views.StaffWeekViewSet, basename="staff-week")
router.register(r"lessons", views.StaffLessonViewSet, basename="staff-lesson")
router.register(r"quizzes", views.StaffWeeklyQuizViewSet, basename="staff-quiz")
router.register(r"projects", views.StaffWeeklyProjectViewSet, basename="staff-project")
router.register(
    r"quiz-questions", views.StaffQuizQuestionViewSet, basename="staff-quiz-question"
)
router.register(
    r"question-choices",
    views.StaffQuestionChoiceViewSet,
    basename="staff-question-choice",
)
router.register(r"plans", views.StaffPlanViewSet, basename="staff-plan")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", views.StaffDashboardView.as_view(), name="staff-dashboard"),
    path(
        "courses/<int:course_id>/bulk-weeks/",
        views.StaffBulkWeekView.as_view(),
        name="staff-bulk-weeks",
    ),
    path(
        "weeks/<int:week_id>/bulk-lessons/",
        views.StaffBulkLessonView.as_view(),
        name="staff-bulk-lessons",
    ),
    path(
        "project-submissions/",
        views.StaffProjectSubmissionView.as_view(),
        name="staff-project-submissions",
    ),
    path(
        "project-submissions/<int:pk>/",
        views.StaffProjectSubmissionDetailView.as_view(),
        name="staff-project-submission-detail",
    ),
]
