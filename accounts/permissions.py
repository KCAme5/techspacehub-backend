# accounts/permissions.py
from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Allows access only to staff (is_staff=True) or superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
