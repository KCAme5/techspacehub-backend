from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .audits.views import AuditOrderViewSet
from .websites.views import WebsiteOrderViewSet

router = DefaultRouter()
router.register(r'audits', AuditOrderViewSet, basename='audit-order')
router.register(r'websites', WebsiteOrderViewSet, basename='website-order')

urlpatterns = [
    path('', include(router.urls)),
]
