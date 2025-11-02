"""from rest_framework import generics, permissions, status
from .models import Resource, UserBookProgress
from .serializers import ResourceSerializer, UserBookProgressSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from courses.models import Subscription


class ResourceListView(generics.ListAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Get user plan and subscriptions
        sub = Subscription.objects.filter(user=user, is_active=True).first()
        plan = sub.plan.upper() if sub else "FREE"

        # FREE: only public resources
        if plan == "FREE":
            return Resource.objects.filter(is_public=True)

        # BASIC/PRO: only resources related to enrolled courses
        enrolled_courses = Subscription.objects.filter(
            user=user, is_active=True
        ).values_list("course", flat=True)
        return Resource.objects.filter(course_id__in=enrolled_courses)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


# ✅ NEW: Single Resource Detail View
class ResourceDetailView(generics.RetrieveAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Resource.objects.all()

    def retrieve(self, request, *args, **kwargs):
        resource = self.get_object()
        user = request.user

        sub = Subscription.objects.filter(
            user=user, course=resource.course, is_active=True
        ).first()
        plan = sub.plan.upper() if sub else "FREE"


        if plan == "FREE" and not resource.is_public:
            return Response(
                {"detail": "Upgrade your plan to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(resource)
        return Response(serializer.data)


class UserBookProgressListView(generics.ListAPIView):
    serializer_class = UserBookProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserBookProgress.objects.filter(user=self.request.user)


class OpenBookView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, book_id):
        progress, created = UserBookProgress.objects.get_or_create(
            user=request.user, book_id=book_id
        )
        progress.is_open = True
        progress.save()
        return Response({"message": "Book opened"})


class CloseBookView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, book_id):
        try:
            progress = UserBookProgress.objects.get(user=request.user, book_id=book_id)
            progress.is_open = False
            progress.save()
            return Response({"message": "Book closed"})
        except UserBookProgress.DoesNotExist:
            return Response({"error": "Book not found for user"}, status=404)
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Resource, UserBookProgress, ResourceViewLog, FavoriteResource
from .serializers import (
    ResourceSerializer,
    UserBookProgressSerializer,
    ResourceViewLogSerializer,
    FavoriteResourceSerializer,
)


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all().order_by("-upload_date")
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # Show all public + enrolled resources (for now: all)
            return Resource.objects.all()
        return Resource.objects.filter(is_public=True)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def view_log(self, request, pk=None):
        resource = self.get_object()
        ResourceViewLog.objects.create(
            user=request.user, resource=resource, action="viewed"
        )
        resource.view_count += 1
        resource.save()
        return Response({"message": "View logged successfully."})

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def download_log(self, request, pk=None):
        resource = self.get_object()
        ResourceViewLog.objects.create(
            user=request.user, resource=resource, action="downloaded"
        )
        return Response({"message": "Download logged successfully."})

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def toggle_favorite(self, request, pk=None):
        resource = self.get_object()
        favorite, created = FavoriteResource.objects.get_or_create(
            user=request.user, resource=resource
        )
        if not created:
            favorite.delete()
            return Response({"message": "Removed from favorites."})
        return Response({"message": "Added to favorites."})


class UserBookProgressViewSet(viewsets.ModelViewSet):
    serializer_class = UserBookProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserBookProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ResourceViewLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ResourceViewLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ResourceViewLog.objects.filter(user=self.request.user)


class FavoriteResourceViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FavoriteResource.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
