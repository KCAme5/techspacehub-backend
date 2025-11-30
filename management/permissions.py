from rest_framework import permissions


class IsManagement(permissions.BasePermission):
    """
    Permission check for management users only.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "management"
        )


class IsManagementOrReadOnly(permissions.BasePermission):
    """
    Management has full access, others have read-only.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "management"
        )
