from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .audits.views import AuditOrderViewSet
from .websites.views import WebsiteOrderViewSet
from .websites.views_serve import serve_generated_website
from .websites.views_chat import WebsiteAIChatViewSet

router = DefaultRouter()
router.register(r"audits", AuditOrderViewSet, basename="audit-order")
router.register(r"websites", WebsiteOrderViewSet, basename="website-order")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "websites/<uuid:order_id>/preview/",
        serve_generated_website,
        name="website-preview",
    ),
    path(
        "websites/<uuid:pk>/chat/history/",
        WebsiteAIChatViewSet.as_view({"get": "conversation_history"}),
    ),
    path(
        "websites/<uuid:pk>/chat/send/",
        WebsiteAIChatViewSet.as_view({"post": "send_message"}),
    ),
    path(
        "websites/<uuid:pk>/chat/revisions/",
        WebsiteAIChatViewSet.as_view({"get": "code_revisions"}),
    ),
    path(
        "websites/<uuid:pk>/chat/rollback/",
        WebsiteAIChatViewSet.as_view({"post": "rollback"}),
    ),
    path(
        "websites/<uuid:pk>/chat/update-code/",
        WebsiteAIChatViewSet.as_view({"post": "update_code_directly"}),
    ),
    path(
        "websites/<uuid:pk>/chat/files/",
        WebsiteAIChatViewSet.as_view({"get": "project_files"}),
    ),
    path(
        "websites/<uuid:pk>/chat/save-file/",
        WebsiteAIChatViewSet.as_view({"post": "save_project_file"}),
    ),
    path(
        "websites/<uuid:pk>/chat/project-type/",
        WebsiteAIChatViewSet.as_view({"post": "set_project_type"}),
    ),
]
