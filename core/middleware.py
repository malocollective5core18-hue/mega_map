from django.http import HttpResponseRedirect, JsonResponse


class PrivateStaffNoStoreMiddleware:
    """Prevent browsers and shared proxies from caching staff/API identity pages."""

    PRIVATE_PREFIXES = ("/staff/", "/admin/", "/api/admin/", "/api/auth/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.PRIVATE_PREFIXES):
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
        return response


class ContentSecurityPolicyReportOnlyMiddleware:
    """Observe CSP incompatibilities without changing page behavior yet."""

    POLICY = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob: https://*.arcgisonline.com "
        "https://server.arcgisonline.com https://*.openstreetmap.org; "
        "connect-src 'self' https://photon.komoot.io https://*.arcgisonline.com "
        "https://server.arcgisonline.com https://*.openstreetmap.org; "
        "font-src 'self' data: https://unpkg.com https://cdnjs.cloudflare.com; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy-Report-Only"] = self.POLICY
        return response


class StaffMFARequiredMiddleware:
    """Require a completed OTP challenge before serving staff data or Django admin pages."""

    STAFF_PREFIXES = ("/api/admin/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        is_staff_area = request.path.startswith(self.STAFF_PREFIXES)
        if request.path == "/admin/login/":
            return HttpResponseRedirect("/staff/")
        if (
            is_staff_area
            and user is not None
            and user.is_authenticated
            and str(user.pk) != str(request.session.get("mfa_verified_user_id", ""))
        ):
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {
                        "error": {
                            "code": "mfa_required",
                            "message": "Complete staff two-step verification to continue.",
                        }
                    },
                    status=403,
                )
            return JsonResponse({"detail": "Staff two-step verification is required."}, status=403)
        return self.get_response(request)
