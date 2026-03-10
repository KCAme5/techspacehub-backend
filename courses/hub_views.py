# courses/hub_views.py
"""
Hub education-path views.
  Learner views   → /api/hub/courses/…  /api/hub/lessons/…
  Staff views     → /api/hub/staff/courses/…  (require IsStaffUser)
"""
from django.utils.text import slugify
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStaffUser
from .models import Course, Level, Module, Lesson, Drill, DrillAnswer, Quiz, QuizOption
from .hub_serializers import (
    CourseHubSerializer, LevelSerializer, ModuleLearnerSerializer,
    LessonLearnerSerializer, DrillLearnerSerializer,
    QuizLearnerSerializer, QuizOptionLearnerSerializer,
    CourseStaffSerializer, LevelStaffSerializer, ModuleStaffSerializer,
    LessonStaffSerializer, DrillStaffSerializer, QuizStaffSerializer,
)


# ─────────────────────── LEARNER VIEWS ───────────────────────────────────

class HubCourseListView(generics.ListAPIView):
    """GET /api/hub/courses/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = CourseHubSerializer

    def get_queryset(self):
        return Course.objects.filter(is_published=True).prefetch_related('levels')


class HubCourseDetailView(generics.RetrieveAPIView):
    """GET /api/hub/courses/<slug>/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = CourseHubSerializer
    lookup_field       = 'slug'

    def get_queryset(self):
        return Course.objects.filter(is_published=True).prefetch_related('levels')


class HubModulesView(APIView):
    """
    GET /api/hub/courses/<course_slug>/levels/<level_slug>/modules/
    Returns modules with progress state (calls get_level_progress_state).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_slug, level_slug):
        try:
            level = Level.objects.get(
                course__slug=course_slug,
                slug=level_slug,
                is_published=True,
            )
        except Level.DoesNotExist:
            return Response({'detail': 'Level not found.'}, status=status.HTTP_404_NOT_FOUND)

        from progress.services import get_level_progress_state
        data = get_level_progress_state(request.user, level)
        return Response(data)


class HubLessonDetailView(generics.RetrieveAPIView):
    """GET /api/hub/lessons/<id>/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = LessonLearnerSerializer

    def get_queryset(self):
        return Lesson.objects.filter(is_published=True).prefetch_related('drills')


class HubCheckDrillView(APIView):
    """
    POST /api/hub/lessons/<id>/check-drill/
    Body: { "drill_id": 1, "answer": "ls -la" }
    Returns: { "correct": true/false }
    Drill answers are validated server-side only.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        drill_id = request.data.get('drill_id')
        answer   = request.data.get('answer', '').strip()

        try:
            drill = Drill.objects.get(pk=drill_id, lesson_id=pk)
        except Drill.DoesNotExist:
            return Response({'detail': 'Drill not found.'}, status=status.HTTP_404_NOT_FOUND)

        correct = drill.answers.filter(
            **({'answer__iexact': answer})
        ).exists() or drill.answers.filter(
            is_case_sensitive=True, answer=answer
        ).exists() or drill.answers.filter(
            is_case_sensitive=False, answer__iexact=answer
        ).exists()

        return Response({'correct': correct})


class HubLessonQuizView(APIView):
    """GET /api/hub/lessons/<id>/quiz/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            quiz = Quiz.objects.get(lesson_id=pk)
        except Quiz.DoesNotExist:
            return Response({'detail': 'No quiz for this lesson.'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(QuizLearnerSerializer(quiz).data)


class HubQuizSubmitView(APIView):
    """
    POST /api/hub/lessons/<id>/quiz/submit/
    Body: { "question_id": 1, "answers": { "question_id": selected_option_id, ... } }
    Since currently Quiz model is 1 per lesson with multiple options,
    we'll handle it based on how many questions are actually in the quiz model.
    Actually the Quiz model seems to be a single question-and-options set.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            quiz = Quiz.objects.get(lesson_id=pk)
        except Quiz.DoesNotExist:
            return Response({'detail': 'No quiz for this lesson.'}, status=status.HTTP_404_NOT_FOUND)

        selected_option_id = request.data.get('option_id')
        if not selected_option_id:
            # Fallback for the multiple answers format just in case
            answers = request.data.get('answers', {})
            selected_option_id = answers.get(str(quiz.id)) or answers.get(quiz.id)

        try:
            selected_option = QuizOption.objects.get(pk=selected_option_id, quiz=quiz)
        except QuizOption.DoesNotExist:
            return Response({'detail': 'Invalid option.'}, status=status.HTTP_400_BAD_REQUEST)

        is_correct = selected_option.is_correct
        xp_awarded = 0
        
        if is_correct:
            # Award XP if not already completed
            from progress.models import UserLessonProgress
            prog, created = UserLessonProgress.objects.get_or_create(
                user=request.user, lesson_id=pk
            )
            if not prog.quiz_completed:
                prog.quiz_completed = True
                xp_awarded = 50 # Standard quiz XP
                prog.points_earned += xp_awarded
                prog.completed = True # Marking lesson as completed too if quiz pass
                prog.save()
                
                # Update total points
                from progress.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.total_points += xp_awarded
                profile.save()

        return Response({
            'correct': is_correct,
            'xp_awarded': xp_awarded > 0,
            'xp_amount': xp_awarded,
            'explanation': quiz.explanation if is_correct else None
        })


class HubLessonCompleteView(APIView):
    """POST /api/hub/lessons/<id>/complete/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            lesson = Lesson.objects.get(pk=pk, is_published=True)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

        from progress.models import UserLessonProgress, UserProfile
        prog, created = UserLessonProgress.objects.get_or_create(
            user=request.user, lesson=lesson
        )

        xp_awarded = 0
        if not prog.completed:
            prog.completed = True
            xp_awarded = lesson.xp_reward
            prog.points_earned += xp_awarded
            prog.save()

            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.total_points += xp_awarded
            profile.save()

        return Response({
            'completed': True,
            'xp_awarded': xp_awarded > 0,
            'xp_amount': xp_awarded
        })


# ─────────────────────── STAFF VIEWS ─────────────────────────────────────

class StaffCourseListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/hub/staff/courses/"""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_serializer_class(self):
        return CourseStaffSerializer

    def get_queryset(self):
        return Course.objects.all().prefetch_related('levels')

    def perform_create(self, serializer):
        course = serializer.save(created_by=self.request.user)
        
        # Auto-generate the 3 default levels as requested
        default_levels = [
            {'name': 'Beginner', 'level_type': 'beginner', 'order': 1, 'description': 'Foundational concepts and basics.'},
            {'name': 'Intermediate', 'level_type': 'intermediate', 'order': 2, 'description': 'Practical applications and intermediate topics.'},
            {'name': 'Advanced', 'level_type': 'advanced', 'order': 3, 'description': 'Complex scenarios and advanced mastery.'},
        ]
        
        for data in default_levels:
            Level.objects.create(
                course=course,
                name=data['name'],
                level_type=data['level_type'],
                order=data['order'],
                description=data['description'],
                is_published=True
            )


class StaffCourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/hub/staff/courses/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = CourseStaffSerializer
    queryset           = Course.objects.all()


class StaffCoursePublishView(APIView):
    """PATCH /api/hub/staff/courses/<id>/publish/"""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def patch(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        course.is_published = not course.is_published
        course.save(update_fields=['is_published'])
        return Response({'is_published': course.is_published})


class StaffLevelListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/hub/staff/courses/<course_id>/levels/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = LevelStaffSerializer

    def get_queryset(self):
        return Level.objects.filter(course_id=self.kwargs['course_id'])

    def perform_create(self, serializer):
        course = Course.objects.get(pk=self.kwargs['course_id'])
        serializer.save(course=course)


class StaffLevelDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/hub/staff/levels/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = LevelStaffSerializer
    queryset           = Level.objects.all()


class StaffModuleListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/hub/staff/levels/<level_id>/modules/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = ModuleStaffSerializer

    def get_queryset(self):
        return Module.objects.filter(level_id=self.kwargs['level_id'])

    def perform_create(self, serializer):
        level = Level.objects.get(pk=self.kwargs['level_id'])
        serializer.save(level=level)


class StaffModuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/hub/staff/modules/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = ModuleStaffSerializer
    queryset           = Module.objects.all()


class StaffLessonListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/hub/staff/modules/<module_id>/lessons/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = LessonStaffSerializer

    def get_queryset(self):
        return Lesson.objects.filter(module_id=self.kwargs['module_id'])

    def perform_create(self, serializer):
        module = Module.objects.get(pk=self.kwargs['module_id'])
        serializer.save(module=module)


class StaffLessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/hub/staff/lessons/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = LessonStaffSerializer
    queryset           = Lesson.objects.all()


class StaffDrillListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/hub/staff/lessons/<lesson_id>/drills/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = DrillStaffSerializer

    def get_queryset(self):
        return Drill.objects.filter(lesson_id=self.kwargs['lesson_id'])

    def perform_create(self, serializer):
        lesson = Lesson.objects.get(pk=self.kwargs['lesson_id'])
        serializer.save(lesson=lesson)


class StaffDrillDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/hub/staff/drills/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = DrillStaffSerializer
    queryset           = Drill.objects.all()


class StaffQuizView(APIView):
    """GET/POST /api/hub/staff/lessons/<lesson_id>/quiz/"""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request, lesson_id):
        try:
            quiz = Quiz.objects.get(lesson_id=lesson_id)
        except Quiz.DoesNotExist:
            return Response({'detail': 'No quiz yet.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(QuizStaffSerializer(quiz).data)

    def post(self, request, lesson_id):
        lesson = Lesson.objects.get(pk=lesson_id)
        ser = QuizStaffSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(lesson=lesson)
        return Response(ser.data, status=status.HTTP_201_CREATED)


class StaffQuizDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/hub/staff/quizzes/<id>/"""
    permission_classes = [IsAuthenticated, IsStaffUser]
    serializer_class   = QuizStaffSerializer
    queryset           = Quiz.objects.all()


from rest_framework.parsers import MultiPartParser, FormParser

class StaffMediaUploadView(APIView):
    """
    POST /api/hub/staff/media/upload/
    Accepts multipart/form-data with a 'file' field.
    Returns the absolute URL of the uploaded file.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]
    parser_classes    = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.data.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Optionally link to a lesson if lesson_id is provided
        lesson_id = request.data.get('lesson_id')
        lesson = None
        if lesson_id:
            try:
                lesson = Lesson.objects.get(pk=lesson_id)
            except Lesson.DoesNotExist:
                pass

        media = LessonMedia.objects.create(file=file_obj, lesson=lesson)
        
        # Construct absolute URL
        file_url = request.build_absolute_uri(media.file.url)
        return Response({
            'id': media.id,
            'url': file_url,
            'filename': media.file.name
        }, status=status.HTTP_201_CREATED)
