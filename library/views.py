from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db import models
from .models import Resource, UserBookProgress, ResourceViewLog, FavoriteResource
from .serializers import (
    ResourceSerializer,
    UserBookProgressSerializer,
    ResourceViewLogSerializer,
    FavoriteResourceSerializer,
    StaffResourceSerializer,
    StaffResourceCreateSerializer,
)

"""
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
"""


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all().order_by("-upload_date")
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Resource.objects.all()
        user = self.request.user

        # Apply filters
        category = self.request.query_params.get("category")
        course_id = self.request.query_params.get("course")

        if category:
            queryset = queryset.filter(category=category)

        if course_id:
            queryset = queryset.filter(course_id=course_id)

        # Filter by accessibility
        if user.is_authenticated:
            if user.is_staff:
                # Staff can see all resources
                return queryset
            else:
                # Regular users see public resources + their enrolled courses
                from courses.models import (
                    Subscription,
                )  # Import here to avoid circular import

                # Get user's enrolled courses
                enrolled_courses = Subscription.objects.filter(
                    user=user, is_active=True
                ).values_list("course", flat=True)

                # Show public resources OR resources from enrolled courses
                queryset = queryset.filter(
                    models.Q(is_public=True) | models.Q(course_id__in=enrolled_courses)
                )
        else:
            # Anonymous users only see public resources
            queryset = queryset.filter(is_public=True)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # Keep your existing custom actions
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def view_log(self, request, pk=None):
        resource = self.get_object()

        # Check if user can access this resource
        if not resource.is_accessible_by(request.user):
            return Response(
                {"detail": "You don't have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )

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

        # Check if user can access this resource
        if not resource.is_accessible_by(request.user):
            return Response(
                {"detail": "You don't have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ResourceViewLog.objects.create(
            user=request.user, resource=resource, action="downloaded"
        )
        return Response({"message": "Download logged successfully."})

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def toggle_favorite(self, request, pk=None):
        resource = self.get_object()

        # Check if user can access this resource
        if not resource.is_accessible_by(request.user):
            return Response(
                {"detail": "You don't have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )

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


class StaffResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for staff to manage library resources
    """

    queryset = Resource.objects.all().order_by("-upload_date")
    permission_classes = [IsAdminUser]  # Only staff can access

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return StaffResourceCreateSerializer
        return StaffResourceSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """Get available categories"""
        return Response(dict(Resource.CATEGORY_CHOICES))

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get library statistics"""
        total_resources = Resource.objects.count()
        public_resources = Resource.objects.filter(is_public=True).count()
        total_views = (
            Resource.objects.aggregate(total_views=models.Sum("view_count"))[
                "total_views"
            ]
            or 0
        )

        return Response(
            {
                "total_resources": total_resources,
                "public_resources": public_resources,
                "total_views": total_views,
                "categories": dict(Resource.CATEGORY_CHOICES),
            }
        )
