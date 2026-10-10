from rest_framework.permissions import IsAuthenticated

from .security import record_audit


class AuditIsAuthenticated(IsAuthenticated):
    """Log rejected anonymous access attempts without request data."""

    def has_permission(self, request, view):
        allowed = super().has_permission(request, view)
        if not allowed:
            record_audit(
                request=request,
                actor=None,
                action="auth.authorization_denied",
                object_type="StaffEndpoint",
                object_id=request.path,
                metadata={"reason": "anonymous"},
            )
        return allowed
