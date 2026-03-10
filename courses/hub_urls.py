# courses/hub_urls.py
"""
Hub education-path URL patterns.
Registered in cybercraft/urls.py under /api/hub/
"""
from django.urls import path
from . import hub_views as v

app_name = 'hub'

urlpatterns = [
    # ─── Learner endpoints ────────────────────────────────────────────────
    path('courses/',
         v.HubCourseListView.as_view(),
         name='course-list'),
    path('courses/<slug:slug>/',
         v.HubCourseDetailView.as_view(),
         name='course-detail'),
    path('courses/<slug:course_slug>/levels/<slug:level_slug>/modules/',
         v.HubModulesView.as_view(),
         name='modules-with-progress'),
    path('lessons/<int:pk>/',
         v.HubLessonDetailView.as_view(),
         name='lesson-detail'),
    path('lessons/<int:pk>/check-drill/',
         v.HubCheckDrillView.as_view(),
         name='check-drill'),

    # ─── Staff endpoints ──────────────────────────────────────────────────
    # Courses
    path('staff/courses/',
         v.StaffCourseListCreateView.as_view(),
         name='staff-course-list'),
    path('staff/courses/<int:pk>/',
         v.StaffCourseDetailView.as_view(),
         name='staff-course-detail'),
    path('staff/courses/<int:pk>/publish/',
         v.StaffCoursePublishView.as_view(),
         name='staff-course-publish'),

    # Levels
    path('staff/courses/<int:course_id>/levels/',
         v.StaffLevelListCreateView.as_view(),
         name='staff-level-list'),
    path('staff/levels/<int:pk>/',
         v.StaffLevelDetailView.as_view(),
         name='staff-level-detail'),

    # Modules
    path('staff/levels/<int:level_id>/modules/',
         v.StaffModuleListCreateView.as_view(),
         name='staff-module-list'),
    path('staff/modules/<int:pk>/',
         v.StaffModuleDetailView.as_view(),
         name='staff-module-detail'),

    # Lessons
    path('staff/modules/<int:module_id>/lessons/',
         v.StaffLessonListCreateView.as_view(),
         name='staff-lesson-list'),
    path('staff/lessons/<int:pk>/',
         v.StaffLessonDetailView.as_view(),
         name='staff-lesson-detail'),

    # Drills
    path('staff/lessons/<int:lesson_id>/drills/',
         v.StaffDrillListCreateView.as_view(),
         name='staff-drill-list'),
    path('staff/drills/<int:pk>/',
         v.StaffDrillDetailView.as_view(),
         name='staff-drill-detail'),

    # Quizzes
    path('staff/lessons/<int:lesson_id>/quiz/',
         v.StaffQuizView.as_view(),
         name='staff-quiz'),
    path('staff/quizzes/<int:pk>/',
         v.StaffQuizDetailView.as_view(),
         name='staff-quiz-detail'),
    
    # Media
    path('staff/media/upload/',
         v.StaffMediaUploadView.as_view(),
         name='staff-media-upload'),
]
