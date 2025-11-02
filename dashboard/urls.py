from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("library/", views.dashboard_library, name="dashboard-library"),
    path("referral/", views.dashboard_referral, name="dashboard-referral"),
    path(
        "payment-status/",
        views.dashboard_payment_status,
        name="dashboard-payment-status",
    ),
    path("progress/", views.UserDashboardProgressView.as_view(), name="user-progress"),
    path(
        "recent-activity/", views.RecentActivityView.as_view(), name="recent-activity"
    ),
    path("stats/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path(
        "continue-learning/",
        views.ContinueLearningView.as_view(),
        name="continue-learning",
    ),
]
