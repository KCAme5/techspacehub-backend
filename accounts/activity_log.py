"""
Activity Logging Utility
Centralized helper functions for logging platform activities.
"""
from accounts.models import ActivityLog


def get_client_ip(request):
    """Extract client IP address from request, handling proxies."""
    ip = request.META.get("HTTP_X_FORWARDED_FOR")
    if ip:
        ip = ip.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request):
    """Extract user agent from request."""
    return request.META.get("HTTP_USER_AGENT", "")[:1000]  # Limit length


def log_activity(
    user=None,
    action=None,
    details=None,
    request=None,
    ip_address=None,
    user_agent=None,
    severity="info",
):
    """
    Log a platform activity to the ActivityLog model.
    
    Args:
        user: User instance (can be None for anonymous actions)
        action: Action type (must match ActivityLog.ACTION_CHOICES)
        details: Dict with additional metadata
        request: Django request object (auto-extracts IP and user agent)
        ip_address: Manual IP address (if request not provided)
        user_agent: Manual user agent (if request not provided)
        severity: 'info', 'warning', or 'critical'
    
    Returns:
        ActivityLog instance
    """
    if details is None:
        details = {}
    
    # Auto-extract from request if provided
    if request:
        if not ip_address:
            ip_address = get_client_ip(request)
        if not user_agent:
            user_agent = get_user_agent(request)
    
    try:
        log_entry = ActivityLog.objects.create(
            user=user,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
        )
        return log_entry
    except Exception as e:
        # Fail silently to avoid breaking functionality
        # Log to console for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create activity log: {str(e)}")
        return None


def log_authentication(user, action, request, success=True, details=None):
    """Helper for logging authentication events."""
    if details is None:
        details = {}
    
    details["success"] = success
    
    severity = "info" if success else "warning"
    
    return log_activity(
        user=user,
        action=action,
        details=details,
        request=request,
        severity=severity,
    )


def log_financial(user, action, amount, currency, request, details=None):
    """Helper for logging financial transactions."""
    if details is None:
        details = {}
    
    details.update({
        "amount": str(amount),
        "currency": currency,
    })
    
    return log_activity(
        user=user,
        action=action,
        details=details,
        request=request,
        severity="info",
    )


def log_security_event(user, action, request, details=None):
    """Helper for logging security-related events."""
    return log_activity(
        user=user,
        action=action,
        details=details or {},
        request=request,
        severity="critical",
    )
