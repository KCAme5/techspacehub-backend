from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .audits.views import AuditRequestViewSet
from .websites.views import WebsiteOrderViewSet

router = DefaultRouter()
router.register(r'audits', AuditRequestViewSet, basename='audit-request')
router.register(r'websites', WebsiteOrderViewSet, basename='website-order')

urlpatterns = [
    path('', include(router.urls)),
]
