"""Print privacy-safe counts that help diagnose missing dashboard records."""

import hashlib
import json
import os
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Case, Count, F, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.models import AuditLog, BusinessLocation, Consent, CustomerBusiness, ProviderCode, VerificationSession


class Command(BaseCommand):
    help = "Print masked counts and deployment/database metadata for dashboard diagnosis."

    def handle(self, *args, **options):
        now = timezone.now()
        first_day = timezone.localdate() - timedelta(days=13)
        start = timezone.make_aware(datetime.combine(first_day, time.min))
        effective_status = Case(
            When(status=ProviderCode.Status.REVOKED, then=Value("revoked")),
            When(status=ProviderCode.Status.EXPIRED, then=Value("expired")),
            When(status=ProviderCode.Status.ACTIVE, expires_at__lte=now, then=Value("expired")),
            When(
                status=ProviderCode.Status.ACTIVE,
                reusable=False,
                use_count__gte=F("max_uses"),
                then=Value("used"),
            ),
            When(status=ProviderCode.Status.ACTIVE, then=Value("active")),
            default=F("status"),
        )
        host = str(connection.settings_dict.get("HOST") or "")
        host_fingerprint = (
            "sha256:" + hashlib.sha256(host.encode("utf-8")).hexdigest()[:10]
            if host
            else None
        )
        latest_migration = (
            MigrationRecorder.Migration.objects.using(connection.alias)
            .order_by("-applied", "-app", "-name")
            .values("app", "name", "applied")
            .first()
        )

        business_by_day = {
            row["day"].isoformat(): row["count"]
            for row in CustomerBusiness.objects.filter(created_at__gte=start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("pk"))
            .order_by("day")
        }
        last_14_days = {
            (timezone.localdate() - timedelta(days=offset)).isoformat(): 0
            for offset in range(13, -1, -1)
        }
        last_14_days.update(business_by_day)

        report = {
            "database": {
                "vendor": connection.vendor,
                "host_fingerprint": host_fingerprint,
            },
            "deployed_commit": os.environ.get("RENDER_GIT_COMMIT")
            or os.environ.get("SOURCE_VERSION"),
            "latest_migration_applied": (
                {
                    "app": latest_migration["app"],
                    "name": latest_migration["name"],
                    "applied_at": timezone.localtime(latest_migration["applied"]).isoformat(),
                }
                if latest_migration
                else None
            ),
            "provider_codes_by_effective_status": {
                row["diagnostic_status"]: row["count"]
                for row in ProviderCode.objects.annotate(
                    diagnostic_status=effective_status
                )
                .values("diagnostic_status")
                .annotate(count=Count("pk"))
                .order_by("diagnostic_status")
            },
            "verification_sessions": {
                "used": VerificationSession.objects.filter(used_at__isnull=False).count(),
                "unused_valid": VerificationSession.objects.filter(
                    used_at__isnull=True, expires_at__gt=now
                ).count(),
                "unused_expired": VerificationSession.objects.filter(
                    used_at__isnull=True, expires_at__lte=now
                ).count(),
            },
            "businesses_by_status": {
                row["status"]: row["count"]
                for row in CustomerBusiness.objects.values("status")
                .annotate(count=Count("pk"))
                .order_by("status")
            },
            "businesses_created_by_day_last_14_days": last_14_days,
            "locations": {
                "present": CustomerBusiness.objects.filter(location__isnull=False).count(),
                "null": CustomerBusiness.objects.filter(location__isnull=True).count(),
            },
            "consents": {
                "present": CustomerBusiness.objects.filter(consent__isnull=False).count(),
                "null": CustomerBusiness.objects.filter(consent__isnull=True).count(),
            },
            "audit_events_by_action_last_14_days": {
                row["action"]: row["count"]
                for row in AuditLog.objects.filter(timestamp__gte=start)
                .values("action")
                .annotate(count=Count("pk"))
                .order_by("action")
            },
        }
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
