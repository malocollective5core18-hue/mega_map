from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import StaffMFAFailure, StaffMFARecoveryCode
from .security import record_audit


def is_staff_user(user):
    return bool(
        user.is_active
        and (
            user.is_superuser
            or user.groups.filter(
                name__in=("dispatcher", "admin", "service_provider", "field_team")
            ).exists()
        )
    )


def current_staff_device(user, *, confirmed=True):
    return TOTPDevice.objects.filter(user=user, confirmed=confirmed).order_by("pk").first()


def is_mfa_verified(request):
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and str(request.session.get("mfa_verified_user_id", "")) == str(user.pk)
    )


def pending_mfa_user(request):
    user_id = request.session.get("mfa_pending_user_id")
    expires = request.session.get("mfa_pending_expires_at")
    if not user_id or not expires or float(expires) <= timezone.now().timestamp():
        request.session.pop("mfa_pending_user_id", None)
        request.session.pop("mfa_pending_expires_at", None)
        return None
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    return user if user and is_staff_user(user) else None


def mfa_locked(user):
    state = StaffMFAFailure.objects.filter(user=user).first()
    return bool(state and state.locked_until and state.locked_until > timezone.now())


def record_mfa_failure(request, user, reason):
    state, _ = StaffMFAFailure.objects.get_or_create(user=user)
    now = timezone.now()
    if state.locked_until and state.locked_until > now:
        return True
    state.failures += 1
    limit = settings.MFA_LOCKOUT_FAILURES
    if state.failures >= limit:
        state.failures = 0
        state.locked_until = now + timedelta(minutes=settings.MFA_LOCKOUT_MINUTES)
    state.save(update_fields=["failures", "locked_until", "updated_at"])
    record_audit(
        request=request,
        actor=user,
        action="auth.mfa_failed",
        object_type="User",
        object_id=user.pk,
        metadata={"reason": reason},
    )
    return bool(state.locked_until and state.locked_until > now)


def clear_mfa_failures(user):
    StaffMFAFailure.objects.filter(user=user).delete()


def establish_verified_session(request, user, *, method):
    login(request._request, user)
    request.session["mfa_verified_user_id"] = str(user.pk)
    request.session.pop("mfa_pending_user_id", None)
    request.session.pop("mfa_pending_expires_at", None)
    clear_mfa_failures(user)
    record_audit(
        request=request,
        actor=user,
        action="auth.mfa_succeeded",
        object_type="User",
        object_id=user.pk,
        metadata={"method": method},
    )


def issue_recovery_codes(user, count=10):
    import secrets

    StaffMFARecoveryCode.objects.filter(user=user, used_at__isnull=True).delete()
    plain_codes = [secrets.token_hex(6).upper() for _ in range(count)]
    StaffMFARecoveryCode.objects.bulk_create(
        [StaffMFARecoveryCode(user=user, code_hash=make_password(code)) for code in plain_codes]
    )
    return plain_codes


def consume_recovery_code(user, raw_code):
    if not isinstance(raw_code, str) or not raw_code or len(raw_code) > 32:
        return False
    now = timezone.now()
    with transaction.atomic():
        rows = StaffMFARecoveryCode.objects.select_for_update().filter(
            user=user, used_at__isnull=True
        )
        for row in rows.order_by("pk"):
            if check_password(raw_code.strip().upper(), row.code_hash):
                row.used_at = now
                row.save(update_fields=["used_at"])
                return True
    return False
