"""
URL configuration for cybercraft project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

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
    # path("api/", include("labs.urls")),
    path("api/payments/", include("billing.urls")),
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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
