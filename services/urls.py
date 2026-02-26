from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .audits.views import AuditOrderViewSet
from .websites.views import WebsiteOrderViewSet
from .websites.views_serve import serve_generated_website

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
]
