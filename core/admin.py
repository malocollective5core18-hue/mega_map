from django.contrib import admin

from .models import AuditLog, ProviderCode, VerificationSession


class SuperuserOnlyAdminSite(admin.AdminSite):
    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser


admin.site.__class__ = SuperuserOnlyAdminSite


@admin.register(ProviderCode)
class ProviderCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "status", "expires_at", "use_count", "max_uses", "created_by")
    list_filter = ("status",)
    search_fields = ("label",)
    readonly_fields = ("code_hash", "target_phone_hash", "target_phone_last4", "use_count", "created_at", "revoked_at")

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False


@admin.register(VerificationSession)
class VerificationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "provider_code", "expires_at", "used_at", "created_at")
    readonly_fields = ("provider_code", "token_hash", "expires_at", "used_at", "created_at", "ip_hash")

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "object_type", "object_id")
    list_filter = ("action", "object_type")
    readonly_fields = ("actor", "action", "object_type", "object_id", "timestamp", "ip_hash")
    actions = None

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
