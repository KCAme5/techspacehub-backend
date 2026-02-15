from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, Sum, Count
from django.db.models.functions import Coalesce
from django.http import HttpResponse
import csv
from datetime import datetime, timedelta
from django.utils import timezone
from .permissions import IsManagement
from .serializers import (
    UserManagementSerializer,
    CourseManagementSerializer,
    PaymentManagementSerializer,
    ActivityLogSerializer,
)
from .utils import (
    get_dashboard_overview,
    get_revenue_trend,
    get_enrollment_trend,
    get_course_distribution,
    get_recent_activity,
)
from courses.models import Course, Enrollment
from billing.models import Payment
from accounts.models import ActivityLog
from accounts.activity_log import log_activity

User = get_user_model()


class DashboardOverviewViewSet(viewsets.ViewSet):
    """Main dashboard statistics"""

    permission_classes = [IsAuthenticated, IsManagement]

    def list(self, request):
        """Get dashboard overview"""
        data = get_dashboard_overview()
        return Response(data)

    @action(detail=False, methods=["get"])
    def revenue_trend(self, request):
        """Get revenue trend"""
        days = int(request.query_params.get("days", 30))
        data = get_revenue_trend(days)
        return Response(data)

    @action(detail=False, methods=["get"])
    def enrollment_trend(self, request):
        """Get enrollment trend"""
        days = int(request.query_params.get("days", 30))
        data = get_enrollment_trend(days)
        return Response(data)

    @action(detail=False, methods=["get"])
    def debug_migrations(self, request):
        """Debug migrations in production"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('showmigrations', stdout=out)
        
        # Also check if table exists
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'accounts_activitylog'")
            table_exists = cursor.fetchone()[0] > 0
            
        return Response({
            "migrations": out.getvalue(),
            "table_exists": table_exists
        })

    @action(detail=False, methods=["get"])
    def course_distribution(self, request):
        """Get course enrollment distribution"""
        data = get_course_distribution()
        return Response(data)

    @action(detail=False, methods=["get"])
    def recent_activity(self, request):
        """Get recent platform activity"""
        limit = int(request.query_params.get("limit", 20))
        data = get_recent_activity(limit)
        return Response(data)


class UserManagementViewSet(viewsets.ModelViewSet):
    """User management endpoints"""

    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = UserManagementSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        # Optimized query with annotations to prevent N+1 queries
        queryset = User.objects.annotate(
            annotated_total_enrollments=Count("enrollments", distinct=True),
            annotated_total_spent=Coalesce(
                Sum("payments__amount", filter=Q(payments__status="success")),
                0,
                output_field=models.DecimalField()
            )
        ).select_related("wallet")

        # Filter by role
        role = self.request.query_params.get("role", None)
        if role:
            queryset = queryset.filter(role=role)

        # Filter by status
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        # Search
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            )

        return queryset.order_by("-date_joined")

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend a user"""
        user = self.get_object()
        user.is_active = False
        user.save()
        
        # Log suspension activity
        log_activity(
            user=request.user,
            action="user_suspended",
            details={"suspended_user": user.username, "suspended_user_id": user.id},
            request=request,
            severity="warning"
        )
        
        return Response({"message": f"User {user.username} suspended successfully"})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate a user"""
        user = self.get_object()
        user.is_active = True
        user.save()
        
        # Log activation activity
        log_activity(
            user=request.user,
            action="user_updated",
            details={"activated_user": user.username, "activated_user_id": user.id},
            request=request,
            severity="info"
        )
        
        return Response({"message": f"User {user.username} activated successfully"})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get user statistics"""
        total_users = User.objects.count()
        students = User.objects.filter(role="student").count()
        staff = User.objects.filter(role="staff").count()
        management = User.objects.filter(role="management").count()
        active = User.objects.filter(is_active=True).count()
        inactive = User.objects.filter(is_active=False).count()

        return Response(
            {
                "total": total_users,
                "students": students,
                "staff": staff,
                "management": management,
                "active": active,
                "inactive": inactive,
            }
        )


class CourseManagementViewSet(viewsets.ModelViewSet):
    """Course management endpoints"""

    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = CourseManagementSerializer
    queryset = Course.objects.all()

    def get_queryset(self):
        queryset = Course.objects.all()

        # Filter by active status
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        # Search
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Toggle course active status"""
        course = self.get_object()
        course.is_active = not course.is_active
        course.save()
        status_text = "activated" if course.is_active else "deactivated"
        return Response({"message": f"Course {status_text} successfully"})

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get detailed course analytics"""
        course = self.get_object()

        enrollments = Enrollment.objects.filter(week__course=course)
        total_enrollments = enrollments.count()
        active_enrollments = enrollments.filter(is_active=True).count()
        completed_enrollments = enrollments.filter(completed=True).count()

        revenue = (
            Payment.objects.filter(week__course=course, status="success").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        return Response(
            {
                "total_enrollments": total_enrollments,
                "active_enrollments": active_enrollments,
                "completed_enrollments": completed_enrollments,
                "completion_rate": (
                    round((completed_enrollments / total_enrollments * 100), 2)
                    if total_enrollments > 0
                    else 0
                ),
                "total_revenue": float(revenue),
            }
        )


class PaymentManagementViewSet(viewsets.ModelViewSet):
    """Payment management endpoints"""

    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = PaymentManagementSerializer
    queryset = Payment.objects.all()

    def get_queryset(self):
        queryset = Payment.objects.select_related("user", "week").all()

        # Filter by status
        status_filter = self.request.query_params.get("status", None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by method
        method = self.request.query_params.get("method", None)
        if method:
            queryset = queryset.filter(method=method)

        # Search by user
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
                | Q(transaction_id__icontains=search)
            )

        return queryset.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a pending payment"""
        payment = self.get_object()
        if payment.status != "pending":
            return Response(
                {"error": "Only pending payments can be approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = "success"
        payment.admin_notes = f"Approved by {request.user.username}"
        payment.save()

        return Response({"message": "Payment approved successfully"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a pending payment"""
        payment = self.get_object()
        if payment.status != "pending":
            return Response(
                {"error": "Only pending payments can be rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "No reason provided")
        payment.status = "failed"
        payment.admin_notes = f"Rejected by {request.user.username}: {reason}"
        payment.save()

        return Response({"message": "Payment rejected successfully"})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get payment statistics"""

        total_revenue = (
            Payment.objects.filter(status="success").aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        pending_count = Payment.objects.filter(status="pending").count()
        pending_amount = (
            Payment.objects.filter(status="pending").aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        success_count = Payment.objects.filter(status="success").count()
        failed_count = Payment.objects.filter(status="failed").count()

        return Response(
            {
                "total_revenue": float(total_revenue),
                "pending_count": pending_count,
                "pending_amount": float(pending_amount),
                "success_count": success_count,
                "failed_count": failed_count,
            }
        )


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Activity log viewing for management (read-only)"""
    
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = ActivityLogSerializer
    queryset = ActivityLog.objects.all()
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related("user").all()
        
        # Filter by user
        user_id = self.request.query_params.get("user_id", None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action type
        action = self.request.query_params.get("action", None)
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by severity
        severity = self.request.query_params.get("severity", None)
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by date range
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)
        
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d")
                end = end + timedelta(days=1)  # Include the entire end date
                queryset = queryset.filter(timestamp__lt=end)
            except ValueError:
                pass
        
        # Search by username, email, IP
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
                | Q(ip_address__icontains=search)
            )
        
        return queryset.order_by("-timestamp")
    
    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        """Export activity logs to CSV"""
        queryset = self.get_queryset()[:1000]  # Limit to 1000 records
        
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="activity_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            "Timestamp",
            "Username",
            "Email",
            "Action",
            "Severity",
            "IP Address",
            "Details"
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.user.username if log.user else "Anonymous",
                log.user.email if log.user else "N/A",
                log.get_action_display(),
                log.get_severity_display(),
                log.ip_address or "N/A",
                str(log.details)
            ])
        
        return response
    
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get activity log statistics"""
        total_logs = ActivityLog.objects.count()
        
        # Count by severity
        critical_count = ActivityLog.objects.filter(severity="critical").count()
        warning_count = ActivityLog.objects.filter(severity="warning").count()
        info_count = ActivityLog.objects.filter(severity="info").count()
        
        # Recent activity (last 24 hours)
        yesterday = timezone.now() - timedelta(days=1)
        recent_count = ActivityLog.objects.filter(timestamp__gte=yesterday).count()
        
        return Response({
            "total_logs": total_logs,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "recent_24h": recent_count,
        })
