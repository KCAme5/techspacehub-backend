from rest_framework import serializers
from django.contrib.auth import get_user_model
from courses.models import Course, Week, Enrollment
from billing.models import Payment
from accounts.models import Wallet, Referral, ActivityLog
from django.db import models

User = get_user_model()


class UserManagementSerializer(serializers.ModelSerializer):
    """Detailed user info for management"""

    total_enrollments = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    last_login_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "subscription_status",
            "subscription_plan",
            "is_active",
            "date_joined",
            "last_login",
            "last_login_display",
            "total_enrollments",
            "total_spent",
            "wallet_balance",
        ]

    def get_total_enrollments(self, obj):
        # Use annotated value if available, else fallback to count()
        return getattr(obj, "annotated_total_enrollments", obj.enrollments.count())

    def get_total_spent(self, obj):
        # Use annotated value if available, else fallback to aggregate
        if hasattr(obj, "annotated_total_spent"):
            return float(obj.annotated_total_spent)
            
        total = obj.payments.filter(status="success").aggregate(
            total=models.Sum("amount")
        )["total"]
        return float(total) if total else 0

    def get_wallet_balance(self, obj):
        # wallet is select_related in get_queryset
        try:
            return float(obj.wallet.balance)
        except:
            return 0

    def get_last_login_display(self, obj):
        if obj.last_login:
            return obj.last_login.strftime("%Y-%m-%d %H:%M")
        return "Never"


class CourseManagementSerializer(serializers.ModelSerializer):
    """Course info with analytics for management"""

    total_weeks = serializers.SerializerMethodField()
    total_enrollments = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    avg_completion_rate = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "thumbnail",
            "is_active",
            "instructor",
            "instructor_name",
            "created_at",
            "updated_at",
            "total_weeks",
            "total_enrollments",
            "total_revenue",
            "avg_completion_rate",
        ]

    def get_total_weeks(self, obj):
        return obj.weeks.count()

    def get_total_enrollments(self, obj):
        return Enrollment.objects.filter(week__course=obj).count()

    def get_total_revenue(self, obj):
        total = Payment.objects.filter(week__course=obj, status="success").aggregate(
            total=models.Sum("amount")
        )["total"]
        return float(total) if total else 0

    def get_avg_completion_rate(self, obj):
        enrollments = Enrollment.objects.filter(week__course=obj)
        if not enrollments.exists():
            return 0
        completed = enrollments.filter(completed=True).count()
        return round((completed / enrollments.count()) * 100, 2)

    def get_instructor_name(self, obj):
        return obj.instructor.username if obj.instructor else "N/A"


class PaymentManagementSerializer(serializers.ModelSerializer):
    """Payment info for management"""

    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    week_title = serializers.CharField(source="week.title", read_only=True)
    course_title = serializers.CharField(source="week.course.title", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "week",
            "week_title",
            "course_title",
            "amount",
            "currency",
            "method",
            "plan",
            "transaction_id",
            "status",
            "mpesa_receipt",
            "created_at",
            "updated_at",
            "admin_notes",
        ]


class ActivityLogSerializer(serializers.ModelSerializer):
    """Activity log for management dashboard audit trail"""

    username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    timestamp_display = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "username",
            "user_email",
            "action",
            "action_display",
            "details",
            "ip_address",
            "user_agent",
            "severity",
            "severity_display",
            "timestamp",
            "timestamp_display",
        ]

    def get_timestamp_display(self, obj):
        return obj.timestamp.strftime("%Y-%m-%d %H:%M:%S")
