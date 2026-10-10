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
