# staff_dashboard/views.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStaffUser
from courses.models import Course, Level, Module, Lesson
from payments.models import Payment


class StaffDashboardStatsView(APIView):
    """
    GET /api/hub/staff/dashboard/
    Aggregated stats for the staff dashboard.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        total_courses  = Course.objects.filter(is_published=True).count()
        total_users    = User.objects.count()
        total_revenue  = Payment.objects.filter(status='completed').aggregate(
            total=__import__('django.db.models', fromlist=['Sum']).Sum('amount')
        )['total'] or 0

        recent_payments = Payment.objects.filter(status='completed').order_by('-completed_at')[:5]

        return Response({
            'total_courses':       total_courses,
            'total_users':         total_users,
            'total_revenue_kes':   float(total_revenue),
            'recent_payments': [
                {
                    'id':            p.id,
                    'user':          p.user.username,
                    'payment_for':   p.payment_for,
                    'amount':        float(p.amount),
                    'completed_at':  p.completed_at,
                }
                for p in recent_payments
            ],
        })


class StaffLearnerListView(APIView):
    """
    GET /api/hub/staff/learners/
    List all learners with basic enrollment stats.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        User = get_user_model()

        queryset = User.objects.filter(role='student').annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-date_joined')

        # Simple search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                __import__('django.db.models').Q(username__icontains=search) | 
                __import__('django.db.models').Q(email__icontains=search)
            )

        return Response([
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'date_joined': u.date_joined,
                'enrollments': u.enrollment_count,
                'is_active': u.is_active
            }
            for u in queryset[:100] # Limit for performance
        ])


class StaffPaymentListView(APIView):
    """
    GET /api/hub/staff/payments/
    List all hub payments.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        queryset = Payment.objects.all().select_related('user').order_by('-created_at')

        return Response([
            {
                'id': p.id,
                'user': p.user.username,
                'amount': float(p.amount),
                'status': p.status,
                'payment_for': p.payment_for,
                'transaction_id': p.transaction_id,
                'created_at': p.created_at,
                'completed_at': p.completed_at
            }
            for p in queryset[:100]
        ])
