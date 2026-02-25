from rest_framework import permissions

class IsOrderOwner(permissions.BasePermission):
    """
    Only the client who created the order can access it.
    """
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user

class IsAssignedAgent(permissions.BasePermission):
    """
    For manned orders, only the assigned agent can access.
    """
    def has_object_permission(self, request, view, obj):
        # This assumes the concrete model has an 'agent' or 'assigned_agent' field
        # or we check via AgentAssignment model later.
        if hasattr(obj, 'agent'):
            return obj.agent == request.user
        return False

class IsServiceStaff(permissions.BasePermission):
    """
    Admin/Management users have full access.
    """
    def has_permission(self, request, view):
        return request.user.role in ['management', 'staff'] or request.user.is_staff

class IsOwnerOrStaff(permissions.BasePermission):
    """
    Combined permission for Order Owner or Service Staff.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff check
        if request.user.role in ['management', 'staff'] or request.user.is_staff:
            return True
        # Owner check
        return hasattr(obj, 'client') and obj.client == request.user

class CanClaimOrder(permissions.BasePermission):
    """
    Qualified agents (logic checks labs/courses completion later).
    """
    def has_permission(self, request, view):
        # Placeholder logic: Check if user is staff/agent role
        return request.user.role == 'staff'
