from django.urls import path

from . import views

urlpatterns = [
    path("public/shops", views.public_shops, name="public-shops"),
    path("public/shops/search", views.public_shop_search, name="public-shop-search"),
    path("public/demand-cells", views.public_demand_cells, name="public-demand-cells"),
    path("public/config", views.public_config, name="public-config"),
    path("provider-codes/verify", views.verify_code, name="provider-code-verify"),
    path("location-submissions", views.submit_location, name="location-submission"),
    path("customer/profile", views.update_customer_profile, name="customer-profile"),
    path("auth/csrf", views.auth_csrf, name="auth-csrf"),
    path("auth/login", views.auth_login, name="auth-login"),
    path("auth/logout", views.auth_logout, name="auth-logout"),
    path("admin/staff-users", views.admin_staff_users, name="admin-staff-users"),
    path("admin/businesses", views.admin_businesses, name="admin-businesses"),
    path(
        "admin/businesses/<uuid:business_id>",
        views.admin_business_detail,
        name="admin-business-detail",
    ),
    path(
        "admin/businesses/<uuid:business_id>/visits",
        views.admin_business_visits,
        name="admin-business-visits",
    ),
    path("admin/export.csv", views.admin_export, name="admin-export"),
    path("admin/provider-codes", views.admin_provider_codes, name="admin-provider-codes"),
    path(
        "admin/provider-codes/<int:code_id>/revoke",
        views.admin_revoke_code,
        name="admin-provider-code-revoke",
    ),
    path("admin/audit-log", views.admin_audit_log, name="admin-audit-log"),
]
