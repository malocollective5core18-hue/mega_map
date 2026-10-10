from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path
from django.views.generic import TemplateView


def staff_home(request):
    if request.user.is_authenticated and (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["dispatcher", "admin", "service_provider"]).exists()
    ):
        return render(
            request,
            "staff/dashboard.html",
            {
                "is_admin": request.user.is_superuser
                or request.user.groups.filter(name="admin").exists(),
                "is_superuser": request.user.is_superuser,
                "is_provider": not request.user.is_superuser
                and request.user.groups.filter(name="service_provider").exists(),
            },
        )
    return render(request, "staff/login.html")


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("staff/", staff_home, name="staff-home"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
