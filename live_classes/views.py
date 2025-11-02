# live_classes/views.py
'''from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import LiveClass, LiveClassRecording, LiveClassAttendance
from .serializers import (
    LiveClassSerializer,
    LiveClassRecordingSerializer,
    LiveClassAttendanceSerializer,
)
from .permissions import CanJoinLiveClass


# 🎥 LIST & DETAIL — Live Classes
class LiveClassListView(generics.ListCreateAPIView):
    queryset = LiveClass.objects.all().select_related("course", "instructor")
    serializer_class = LiveClassSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return self.queryset
        return self.queryset.filter(is_cancelled=False)


class LiveClassDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LiveClass.objects.all().select_related("course", "instructor")
    serializer_class = LiveClassSerializer
    permission_classes = [IsAuthenticated]


# 💾 LIST & DETAIL — Recordings
class LiveClassRecordingListView(generics.ListCreateAPIView):
    queryset = LiveClassRecording.objects.all().select_related("live_class")
    serializer_class = LiveClassRecordingSerializer
    permission_classes = [IsAuthenticated]


class LiveClassRecordingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LiveClassRecording.objects.all().select_related("live_class")
    serializer_class = LiveClassRecordingSerializer
    permission_classes = [IsAuthenticated]


# 👥 LIST & DETAIL — Attendance
class LiveClassAttendanceListView(generics.ListCreateAPIView):
    queryset = LiveClassAttendance.objects.all().select_related("live_class", "user")
    serializer_class = LiveClassAttendanceSerializer
    permission_classes = [IsAuthenticated]


class LiveClassAttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LiveClassAttendance.objects.all().select_related("live_class", "user")
    serializer_class = LiveClassAttendanceSerializer
    permission_classes = [IsAuthenticated]


# 🟢 JOIN / LEAVE — Live Class Actions
@api_view(["GET"])
@permission_classes([IsAuthenticated, CanJoinLiveClass])
def join_live_class(request, pk):
    """Return Jitsi join details if user has access"""
    try:
        live_class = LiveClass.objects.get(pk=pk)
        room, url = live_class.ensure_jitsi()
        live_class.save()
        attendance, _ = LiveClassAttendance.objects.get_or_create(
            live_class=live_class,
            user=request.user,
            defaults={"status": "joined", "joined_at": timezone.now()},
        )
        return Response(
            {
                "room": room,
                "url": url,
                "password": live_class.jitsi_password or "",
                "status": attendance.status,
            }
        )
    except LiveClass.DoesNotExist:
        return Response({"error": "Class not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def leave_live_class(request, pk):
    """Mark user as having left the class"""
    try:
        live_class = LiveClass.objects.get(pk=pk)
        attendance = LiveClassAttendance.objects.get(
            live_class=live_class, user=request.user
        )
        attendance.status = "left"
        attendance.left_at = timezone.now()
        attendance.save()
        return Response({"message": "Left successfully"})
    except LiveClassAttendance.DoesNotExist:
        return Response({"error": "Not attending"}, status=404)
    except LiveClass.DoesNotExist:
        return Response({"error": "Class not found"}, status=404)
'''
