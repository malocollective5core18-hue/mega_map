import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuditLog, CodeAttempt, ProviderCode, VerificationSession


def hash_value(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_ip(request):
    return hash_value(request.META.get("REMOTE_ADDR", "")) if request else ""


def record_audit(*, request=None, actor=None, action, object_type, object_id=""):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        ip_hash=hash_ip(request),
    )


def issue_provider_code(*, target_phone, expires_at, max_uses=1, label="", created_by=None):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw_code = "".join(secrets.choice(alphabet) for _ in range(16))
    code = ProviderCode.objects.create(
        code_hash=hash_value(raw_code),
        target_phone_hash=hash_value("provider-phone:" + target_phone),
        target_phone_last4=target_phone[-4:],
        expires_at=expires_at,
        max_uses=max_uses,
        label=label,
        created_by=created_by,
    )
    return code, raw_code


@transaction.atomic
def verify_provider_code(raw_code, target_phone, *, request=None):
    normalized = "".join(raw_code.split()).upper()
    digest = hash_value(normalized)
    CodeAttempt.objects.create(code_hash=digest)
    code = ProviderCode.objects.select_for_update().filter(code_hash=digest).first()
    phone_digest = hash_value("provider-phone:" + target_phone)
    if code is None or not code.accepts() or not hmac.compare_digest(code.target_phone_hash, phone_digest):
        return None
    ttl = min(settings.PROVIDER_CODE_TTL_SECONDS, 30 * 60)
    token = secrets.token_urlsafe(32)
    now = timezone.now()
    VerificationSession.objects.create(
        provider_code=code,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=now + timedelta(seconds=ttl),
        ip_hash=hash_ip(request),
    )
    code.use_count += 1
    code.save(update_fields=["use_count"])
    return token


def code_attempts_throttled(raw_code):
    digest = hash_value("".join(raw_code.split()).upper())
    return CodeAttempt.objects.filter(code_hash=digest, created_at__gte=timezone.now() - timedelta(hours=1)).count() >= 5
