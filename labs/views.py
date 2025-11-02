from rest_framework import generics, permissions
from .models import Lab
from .serializers import LabSerializer
from courses.models import Subscription
from rest_framework.response import Response
from .utils import filter_labs_by_plan


class LabListView(generics.ListAPIView):
    serializer_class = LabSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        plan = "FREE"

        sub = Subscription.objects.filter(user=user, is_active=True).first()
        if sub:
            plan = sub.plan.upper()

        # Filter based on plan
        if plan == "FREE":
            return Lab.objects.filter(is_free=True, is_active=True)
        elif plan == "BASIC":
            return Lab.objects.filter(is_active=True)
        elif plan == "PRO":
            return Lab.objects.filter(is_active=True)
        else:
            return filter_labs_by_plan(Lab.objects.all(), plan)


class LabDetailView(generics.RetrieveAPIView):
    serializer_class = LabSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Lab.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        lab = self.get_object()
        serializer = self.get_serializer(lab)
        data = serializer.data

        user = request.user
        plan = "FREE"

        sub = Subscription.objects.filter(
            user=user, course=lab.course, is_active=True
        ).first()
        if sub:
            plan = sub.plan.upper()

        # Restrict access if not allowed
        if plan == "FREE" and not lab.is_free:
            return Response(
                {"detail": "Upgrade your plan to access this lab."}, status=403
            )

        return Response(data)
