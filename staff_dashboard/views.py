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
