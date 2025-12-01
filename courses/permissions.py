#courses/permissions.py
from rest_framework import permissions


class IsStaffUser(permissions.BasePermission):
    """
    Permission check for staff users.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "staff"
        )


class IsInstructorOrStaff(permissions.BasePermission):
    """
    Permission check for course instructors or staff.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == "staff":
            return True
        return obj.instructor == request.user
