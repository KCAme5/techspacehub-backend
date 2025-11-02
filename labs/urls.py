from django.urls import path
from .views import LabListView, LabDetailView

urlpatterns = [
    path("", LabListView.as_view(), name="lab-list"),
    path("<int:pk>/", LabDetailView.as_view(), name="lab-detail"),
]
