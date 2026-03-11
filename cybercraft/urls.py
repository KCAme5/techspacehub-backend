from django.contrib import admin
from accounts.views import (
    google_callback_fixed,
)
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/courses/", include("courses.urls")),
    path("api/staff/", include("courses.urls_staff")),
    path("api/library/", include("library.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/", include("chat.urls")),
    path("api/management/", include("management.urls")),
    # path("api/", include("labs.urls")),
    path("api/payments/", include("billing.urls")),
    path("api/services/", include("services.urls")),
    # path("api/live/", include("live_classes.urls")),
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("api/auth/social/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path(
        "accounts/google/login/callback/",
        google_callback_fixed,
        name="google_callback_fixed",
    ),
    # ─── Hub education-path endpoints ────────────────────────────────────
    path("api/hub/", include("courses.hub_urls")),
    path("api/hub/progress/", include("progress.urls")),
    path("api/hub/payments/", include("payments.urls")),
    path("api/hub/staff/", include("staff_dashboard.urls")),
    # ─── AI Builder — credit system endpoints ────────────────────────────
    path("api/builder/", include("builder.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
