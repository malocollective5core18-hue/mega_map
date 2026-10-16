from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.urls import include, path

from core.mfa import is_mfa_verified


def healthz(_request):
    return HttpResponse(status=204)


def robots_txt(_request):
    content = "\n".join(
        (
            "User-agent: *",
            "Allow: /",
            "Disallow: /staff/",
            "Disallow: /api/",
            "Disallow: /admin/",
            f"Sitemap: {settings.SITE_URL}/sitemap.xml",
            "",
        )
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def sitemap_xml(_request):
    return HttpResponse(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{settings.SITE_URL}/</loc></url></urlset>",
        content_type="application/xml",
    )


def public_home(request):
    return render(request, "index.html", {"site_url": settings.SITE_URL})


def staff_home(request):
    mfa_verified = is_mfa_verified(request)
    if mfa_verified and (
        request.user.is_superuser
        or request.user.groups.filter(
            name__in=["dispatcher", "admin", "service_provider", "field_team"]
        ).exists()
    ):
        if request.user.is_superuser:
            staff_role = "Superuser"
        else:
            staff_role = next(
                (
                    label
                    for name, label in (
                        ("admin", "Admin assistant"),
                        ("dispatcher", "Dispatcher"),
                        ("service_provider", "Service provider"),
                        ("field_team", "Field team"),
                    )
                    if request.user.groups.filter(name=name).exists()
                ),
                "Staff",
            )
        return render(
            request,
            "staff/dashboard.html",
            {
                "is_admin": request.user.is_superuser
                or request.user.groups.filter(name="admin").exists(),
                "is_superuser": request.user.is_superuser,
                "is_provider": not request.user.is_superuser
                and request.user.groups.filter(name="service_provider").exists(),
                "is_field_team": not request.user.is_superuser
                and request.user.groups.filter(name="field_team").exists(),
                "is_mfa_recovery_owner": bool(
                    settings.MFA_RECOVERY_OWNER_EMAIL
                    and request.user.email.strip().lower() == settings.MFA_RECOVERY_OWNER_EMAIL
                ),
                "staff_role": staff_role,
            },
        )
    return render(request, "staff/login.html")


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("", public_home, name="home"),
    path("staff/", staff_home, name="staff-home"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
