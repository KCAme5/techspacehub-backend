# progress/urls.py
from django.urls import path
from . import views

app_name = 'progress'

urlpatterns = [
    path('level/<int:level_id>/',          views.LevelProgressView.as_view(),   name='level-progress'),
    path('lesson/<int:lesson_id>/complete/', views.CompleteLessonView.as_view(), name='complete-lesson'),
    path('summary/',                        views.ProgressSummaryView.as_view(), name='summary'),
]
