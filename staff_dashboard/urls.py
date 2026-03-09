# staff_dashboard/urls.py
from django.urls import path
from . import views

app_name = 'staff_dashboard'

urlpatterns = [
    path('dashboard/', views.StaffDashboardStatsView.as_view(), name='dashboard'),
]
