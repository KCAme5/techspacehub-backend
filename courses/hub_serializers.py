# courses/hub_serializers.py
"""
Hub education-path serializers.
Learner serializers:  never expose DrillAnswer data.
Staff serializers:    full read/write including correct answers.
"""
from rest_framework import serializers
from .models import (
    Course, Level, Module, Lesson,
    Drill, DrillAnswer, Quiz, QuizOption,
)


# ───────────────────────── LEARNER SERIALIZERS ──────────────────────────
class LevelSimpleSerializer(serializers.ModelSerializer):
    course_slug = serializers.ReadOnlyField(source='course.slug')
    class Meta:
        model = Level
        fields = ['id', 'name', 'slug', 'course_slug']


class ModuleSimpleSerializer(serializers.ModelSerializer):
    level = LevelSimpleSerializer(read_only=True)
    class Meta:
        model = Module
        fields = ['id', 'title', 'level']


class QuizOptionLearnerSerializer(serializers.ModelSerializer):
    """Quiz options shown to learners — NO is_correct included."""
    class Meta:
        model  = QuizOption
        fields = ['id', 'label', 'text', 'order']


class QuizLearnerSerializer(serializers.ModelSerializer):
    """Quiz shown to learners — NO is_correct in options."""
    options = QuizOptionLearnerSerializer(many=True, read_only=True)

    class Meta:
        model  = Quiz
        fields = ['id', 'question', 'explanation', 'options']


class DrillLearnerSerializer(serializers.ModelSerializer):
    """Drills shown to learners — NO answers included."""
    class Meta:
        model  = Drill
        fields = ['id', 'order', 'prompt', 'task', 'hint']


class LessonLearnerSerializer(serializers.ModelSerializer):
    drills = DrillLearnerSerializer(many=True, read_only=True)
    has_quiz = serializers.SerializerMethodField()
    module = ModuleSimpleSerializer(read_only=True)
    drills_count = serializers.SerializerMethodField()
    quiz_count = serializers.SerializerMethodField()

    def get_has_quiz(self, obj):
        return hasattr(obj, 'quiz')

    def get_drills_count(self, obj):
        return obj.drills.count()

    def get_quiz_count(self, obj):
        # Lesson has a OneToOne with Quiz named 'quiz'
        return 1 if hasattr(obj, 'quiz') else 0

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'icon', 'order', 'xp_reward', 'lesson_type',
            'theory_html', 'has_lab', 'lab_language', 'starter_code',
            'notebook_filename', 'terminal_commands', 'drills', 'has_quiz',
            'module', 'drills_count', 'quiz_count',
        ]


class ModuleLearnerSerializer(serializers.ModelSerializer):
    lessons = LessonLearnerSerializer(many=True, read_only=True)

    class Meta:
        model  = Module
        fields = [
            'id', 'title', 'description', 'order', 'icon', 'color',
            'xp_reward', 'single_module_price', 'is_published', 'lessons',
        ]


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Level
        fields = ['id', 'name', 'slug', 'level_type', 'description', 'order', 'is_published']


class CourseHubSerializer(serializers.ModelSerializer):
    levels = LevelSerializer(many=True, read_only=True)

    class Meta:
        model  = Course
        fields = [
            'id', 'title', 'slug', 'domain', 'description',
            'icon', 'color', 'is_published', 'levels',
        ]


# ───────────────────────── STAFF SERIALIZERS ────────────────────────────

class DrillAnswerStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DrillAnswer
        fields = ['id', 'answer', 'is_case_sensitive']


class DrillStaffSerializer(serializers.ModelSerializer):
    answers = DrillAnswerStaffSerializer(many=True)

    class Meta:
        model  = Drill
        fields = ['id', 'order', 'prompt', 'task', 'hint', 'answers']

    def create(self, validated_data):
        answers_data = validated_data.pop('answers', [])
        drill = Drill.objects.create(**validated_data)
        for ans in answers_data:
            DrillAnswer.objects.create(drill=drill, **ans)
        return drill

    def update(self, instance, validated_data):
        answers_data = validated_data.pop('answers', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if answers_data is not None:
            instance.answers.all().delete()
            for ans in answers_data:
                DrillAnswer.objects.create(drill=instance, **ans)
        return instance


class QuizOptionStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model  = QuizOption
        fields = ['id', 'label', 'text', 'is_correct', 'order']


class QuizStaffSerializer(serializers.ModelSerializer):
    options = QuizOptionStaffSerializer(many=True)

    class Meta:
        model  = Quiz
        fields = ['id', 'question', 'explanation', 'options']

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        quiz = Quiz.objects.create(**validated_data)
        for opt in options_data:
            QuizOption.objects.create(quiz=quiz, **opt)
        return quiz

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if options_data is not None:
            instance.options.all().delete()
            for opt in options_data:
                QuizOption.objects.create(quiz=instance, **opt)
        return instance


class LessonStaffSerializer(serializers.ModelSerializer):
    drills = DrillStaffSerializer(many=True, read_only=True)
    quiz   = QuizStaffSerializer(read_only=True)

    class Meta:
        model  = Lesson
        fields = '__all__'
        read_only_fields = ['week', 'module', 'slug', 'is_published']


class ModuleStaffSerializer(serializers.ModelSerializer):
    lessons      = LessonStaffSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    def get_lesson_count(self, obj):
        return obj.lessons.count()

    class Meta:
        model  = Module
        fields = '__all__'
        read_only_fields = ['level', 'is_published']


class LevelStaffSerializer(serializers.ModelSerializer):
    modules = ModuleStaffSerializer(many=True, read_only=True)

    class Meta:
        model  = Level
        fields = '__all__'
        read_only_fields = ['course', 'slug', 'is_published']


class CourseStaffSerializer(serializers.ModelSerializer):
    levels = LevelStaffSerializer(many=True, read_only=True)

    class Meta:
        model  = Course
        fields = '__all__'
        read_only_fields = ['slug', 'is_published', 'created_by']

