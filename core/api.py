from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return Response(
            {"error": {"code": "internal_error", "message": "The request could not be completed."}},
            status=500,
        )
    if isinstance(response.data, dict) and "error" in response.data:
        return response
    if response.status_code == 400:
        code, message = "invalid_request", "Check the submitted fields and try again."
    elif response.status_code == 401:
        code, message = "not_authenticated", "Authentication is required."
    elif response.status_code == 403:
        code, message = "not_allowed", "This action is not allowed."
    elif response.status_code == 404:
        code, message = "not_found", "The requested resource was not found."
    elif response.status_code == 429:
        code, message = "throttled", "Too many requests. Wait a moment and try again."
    else:
        code, message = "request_failed", "The request could not be completed."
    response.data = {"error": {"code": code, "message": message}}
    return response
