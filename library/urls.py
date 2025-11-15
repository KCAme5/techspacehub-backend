from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResourceViewSet,
    UserBookProgressViewSet,
    ResourceViewLogViewSet,
    FavoriteResourceViewSet,
    StaffResourceViewSet,
)

router = DefaultRouter()
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"progress", UserBookProgressViewSet, basename="progress")
router.register(r"views", ResourceViewLogViewSet, basename="views")
router.register(r"favorites", FavoriteResourceViewSet, basename="favorites")

router.register(r"staff/resources", StaffResourceViewSet, basename="staff-resources")

urlpatterns = [
    path("", include(router.urls)),
]
