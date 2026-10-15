import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProviderCode(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    code_hash = models.CharField(max_length=64, unique=True)
    target_phone_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    target_phone_last4 = models.CharField(max_length=4, blank=True, default="")
    business = models.ForeignKey(
        "CustomerBusiness",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_codes",
    )
    legacy_phone_lookup = models.BooleanField(default=True)
    label = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    expires_at = models.DateTimeField()
    max_uses = models.PositiveIntegerField(default=1)
    use_count = models.PositiveIntegerField(default=0)
    reusable = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_provider_codes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]

    def accepts(self):
        return (
            self.status == self.Status.ACTIVE
            and self.expires_at > timezone.now()
            and (self.reusable or self.use_count < self.max_uses)
        )

    def __str__(self):
        return self.label or f"Provider code {self.pk}"


class VerificationSession(models.Model):
    provider_code = models.ForeignKey(
        ProviderCode, on_delete=models.PROTECT, related_name="verification_sessions"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["provider_code", "expires_at"])]

    @property
    def usable(self):
        return self.used_at is None and self.expires_at > timezone.now()


class CustomerBusiness(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        SCHEDULED = "scheduled", "Scheduled"
        SERVED = "served", "Served"
        REJECTED = "rejected", "Rejected"
        DUPLICATE = "duplicate", "Duplicate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_ref = models.CharField(max_length=20, unique=True, db_index=True)
    customer_name = models.CharField(max_length=160)
    business_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, db_index=True)
    phone_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_businesses",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def save(self, *args, **kwargs):
        from .security import hash_value

        self.phone_hash = hash_value("provider-phone:" + self.phone)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"phone_hash"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.public_ref} — {self.business_name}"


class BusinessLocation(models.Model):
    class Source(models.TextChoices):
        GPS = "gps", "GPS"
        MANUAL = "manual_pin", "Manual pin"

    business = models.OneToOneField(
        CustomerBusiness, on_delete=models.CASCADE, related_name="location"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.GPS)
    captured_at = models.DateTimeField(default=timezone.now)
    fix_age_seconds = models.PositiveIntegerField(null=True, blank=True)
    pin_offset_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pin_moved_by_hand = models.BooleanField(default=False)
    address_text = models.CharField(max_length=500, blank=True)
    ward = models.CharField(max_length=160, blank=True)
    district = models.CharField(max_length=160, blank=True)
    region = models.CharField(max_length=160, blank=True)
    corrected_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    corrected_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corrected_business_locations",
    )
    corrected_at = models.DateTimeField(null=True, blank=True)
    team_verified = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["latitude", "longitude"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(latitude__gte=-90, latitude__lte=90),
                name="business_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__gte=-180, longitude__lte=180),
                name="business_longitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(accuracy_m__isnull=True) | models.Q(accuracy_m__gte=0),
                name="business_accuracy_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(pin_offset_m__isnull=True) | models.Q(pin_offset_m__gte=0),
                name="business_pin_offset_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(corrected_lat__isnull=True)
                | (models.Q(corrected_lat__gte=-90) & models.Q(corrected_lat__lte=90)),
                name="corrected_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(corrected_lng__isnull=True)
                | (models.Q(corrected_lng__gte=-180) & models.Q(corrected_lng__lte=180)),
                name="corrected_longitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(corrected_lat__isnull=True) & models.Q(corrected_lng__isnull=True)
                )
                | (models.Q(corrected_lat__isnull=False) & models.Q(corrected_lng__isnull=False)),
                name="corrected_coords_pair",
            ),
        ]

    @property
    def navigation_latitude(self):
        return (
            self.corrected_lat
            if self.team_verified and self.corrected_lat is not None
            else self.latitude
        )

    @property
    def navigation_longitude(self):
        return (
            self.corrected_lng
            if self.team_verified and self.corrected_lng is not None
            else self.longitude
        )


class Consent(models.Model):
    business = models.OneToOneField(
        CustomerBusiness, on_delete=models.CASCADE, related_name="consent"
    )
    privacy_notice_version = models.CharField(max_length=40)
    location_processing = models.BooleanField(default=False)
    public_listing = models.BooleanField(default=False)
    given_at = models.DateTimeField(default=timezone.now)
    ip_hash = models.CharField(max_length=64, blank=True)


class ServiceVisit(models.Model):
    business = models.ForeignKey(CustomerBusiness, on_delete=models.CASCADE, related_name="visits")
    visit_date = models.DateField()
    team = models.CharField(max_length=160, blank=True)
    outcome = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-visit_date", "-created_at"]


class CustomerFlagCase(models.Model):
    class Category(models.TextChoices):
        DUPLICATE = "duplicate", "Possible duplicate"
        SAFETY = "safety", "Safety concern"
        SUSPECTED_FRAUD = "suspected_fraud", "Suspected fraud"
        DATA_CORRECTION = "data_correction", "Data correction needed"
        OTHER = "other", "Other concern"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    business = models.ForeignKey(
        CustomerBusiness,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="flag_cases",
    )
    business_reference = models.CharField(max_length=20)
    category = models.CharField(max_length=24, choices=Category.choices)
    details = models.TextField(max_length=1200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class DemandCell(models.Model):
    cell_id = models.CharField(max_length=80, unique=True)
    geojson = models.JSONField()
    request_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    level = models.CharField(
        max_length=8, choices=[("low", "Low"), ("med", "Medium"), ("high", "High")], default="low"
    )

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["object_type", "object_id", "timestamp"])]


class IdempotencyRecord(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)
    session = models.ForeignKey(
        VerificationSession, null=True, blank=True, on_delete=models.CASCADE
    )
    business = models.ForeignKey(CustomerBusiness, null=True, blank=True, on_delete=models.SET_NULL)
    response_status = models.PositiveSmallIntegerField(default=201)
    response_body = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["created_at"])]


class CodeAttempt(models.Model):
    code_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class StaffMFAFailure(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_failure_state"
    )
    failures = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class StaffMFARecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_recovery_codes"
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"])]
