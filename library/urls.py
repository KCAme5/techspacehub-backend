"""from django.urls import path
from .views import (
    ResourceListView,
    ResourceDetailView,
    UserBookProgressListView,
    OpenBookView,
    CloseBookView,
)

urlpatterns = [
    path("resources/", ResourceListView.as_view(), name="resource-list"),
    path("resources/<int:pk>/", ResourceDetailView.as_view(), name="resource-detail"),
    path("progress/", UserBookProgressListView.as_view(), name="user-book-progress"),
    path("open/<int:book_id>/", OpenBookView.as_view(), name="open-book"),
    path("close/<int:book_id>/", CloseBookView.as_view(), name="close-book"),
]
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResourceViewSet,
    UserBookProgressViewSet,
    ResourceViewLogViewSet,
    FavoriteResourceViewSet,
)

router = DefaultRouter()
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"progress", UserBookProgressViewSet, basename="progress")
router.register(r"views", ResourceViewLogViewSet, basename="views")
router.register(r"favorites", FavoriteResourceViewSet, basename="favorites")

urlpatterns = [
    path("", include(router.urls)),
]
