from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"overview", views.DashboardOverviewViewSet, basename="overview")
router.register(r"users", views.UserManagementViewSet, basename="users")
router.register(r"courses", views.CourseManagementViewSet, basename="courses")
router.register(r"payments", views.PaymentManagementViewSet, basename="payments")

urlpatterns = [
    path("", include(router.urls)),
]
