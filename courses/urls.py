# courses/urls.py
from django.urls import path, include
from . import views

app_name = "courses"

urlpatterns = [
    # Category URLs
    path("categories/", views.CategoryList.as_view(), name="category-list"),
    # Course URLs
    path("courses/", views.CourseList.as_view(), name="course-list"),
    path("courses/<slug:slug>/", views.CourseDetail.as_view(), name="course-detail"),
    path(
        "courses/id/<int:id>/",
        views.CourseDetailById.as_view(),
        name="course-detail-by-id",
    ),
    # Week URLs
    path(
        "courses/<slug:slug>/weeks/",
        views.WeekListByCourse.as_view(),
        name="week-list-by-course",
    ),
    path(
        "courses/<slug:slug>/weeks/<str:level>/",
        views.WeekListByLevel.as_view(),
        name="week-list-by-level",
    ),
    path("weeks/<int:pk>/", views.WeekDetail.as_view(), name="week-detail"),
    # Enrollment URLs
    path("enrollments/", views.EnrollmentList.as_view(), name="enrollment-list"),
    path(
        "enrollments/create/",
        views.EnrollmentCreate.as_view(),
        name="enrollment-create",
    ),
    path(
        "enrolled/",
        views.EnrolledWeekList.as_view(),
        name="enrolled-week-list",
    ),
    # Progress URLs
    path("progress/", views.ProgressList.as_view(), name="progress-list"),
    path(
        "progress/mark-completed/",
        views.ProgressMarkCompleted.as_view(),
        name="progress-mark-completed",
    ),
    path(
        "progress/update-last-viewed/",
        views.ProgressUpdateLastViewed.as_view(),
        name="progress-update-last-viewed",
    ),
    path(
        "weekly-progress/<int:week_id>/",
        views.WeeklyProgressDetail.as_view(),
        name="weekly-progress-detail",
    ),
    # Lesson URLs
    path("lessons/", views.LessonList.as_view(), name="lesson-list"),
    path("lessons/<int:pk>/", views.LessonDetail.as_view(), name="lesson-detail"),
    path(
        "weeks/<int:week_id>/lessons/",
        views.WeekLessonsList.as_view(),
        name="week-lessons-list",
    ),
    # Quiz URLs (Weekly)
    path(
        "weekly-quizzes/<int:quiz_id>/questions/",
        views.WeeklyQuizQuestionsView.as_view(),
        name="weekly-quiz-questions",
    ),
    path(
        "weekly-quizzes/submit/",
        views.WeeklyQuizSubmissionView.as_view(),
        name="weekly-quiz-submit",
    ),
    path(
        "weekly-quizzes/submissions/",
        views.WeeklyQuizSubmissionHistoryView.as_view(),
        name="weekly-quiz-submission-history",
    ),
    path(
        "weekly-quizzes/submissions/<int:quiz_id>/",
        views.WeeklyQuizSubmissionHistoryView.as_view(),
        name="weekly-quiz-submission-history-specific",
    ),
    path(
        "weekly-quizzes/<int:quiz_id>/questions/random/",
        views.WeeklyQuizRandomQuestionsView.as_view(),
        name="weekly-quiz-questions-random",
    ),
    path(
        "weekly-quiz-submissions/<int:pk>/",
        views.WeeklyQuizSubmissionDetailView.as_view(),
        name="weekly-quiz-submission-detail",
    ),
    # Project URLs
    path(
        "project-feedback/<int:project_id>/",
        views.ProjectFeedbackListView.as_view(),
        name="project-feedback-list",
    ),
    path(
        "notifications/",
        views.NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/<int:pk>/mark-read/",
        views.MarkNotificationAsReadView.as_view(),
        name="mark-notification-read",
    ),
    path(
        "weekly-projects/<int:pk>/",
        views.WeeklyProjectDetailView.as_view(),
        name="weekly-project-detail",
    ),
    path(
        "project-submissions/<int:project_id>/",
        views.UserProjectSubmissionsListView.as_view(),
        name="user-project-submissions",
    ),
    path(
        "projects/submit/", views.ProjectSubmissionView.as_view(), name="project-submit"
    ),
    path(
        "project-submissions/<int:pk>/",
        views.ProjectSubmissionDetailView.as_view(),
        name="project-submission-detail",
    ),
    # Plan URLs
    path("plans/", views.PlanList.as_view(), name="plan-list"),
    # Performance URLs
    path(
        "performance/course/<int:course_id>/",
        views.CoursePerformanceView.as_view(),
        name="course-performance",
    ),
    path("staff/", include("courses.urls_staff")),
    # Certificate URLs
    path("certificates/", views.CertificateListView.as_view(), name="certificate-list"),
    path(
        "certificates/generate/",
        views.GenerateCertificateView.as_view(),
        name="generate-certificate",
    ),
    path(
        "certificates/<uuid:certificate_id>/download/",
        views.CertificateDownloadView.as_view(),
        name="download-certificate",
    ),
    path(
        "certificates/<uuid:certificate_id>/preview/",
        views.CertificatePreviewView.as_view(),
        name="certificate-preview",
    ),
    path(
        "courses/completed/",
        views.CompletedCoursesView.as_view(),
        name="completed-courses",
    ),
    # Points and Rewards URLs
    path("points/", views.UserPointsView.as_view(), name="user-points"),
    path(
        "points/transactions/",
        views.PointTransactionListView.as_view(),
        name="point-transactions",
    ),
    path("rewards/", views.RewardListView.as_view(), name="reward-list"),
    path(
        "rewards/redemptions/",
        views.RewardRedemptionListView.as_view(),
        name="reward-redemption-list",
    ),
    path(
        "rewards/redemptions/create/",
        views.RewardRedemptionCreateView.as_view(),
        name="reward-redemption-create",
    ),
]
