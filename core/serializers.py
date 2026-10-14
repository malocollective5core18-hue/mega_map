import re
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers


def normalize_phone(value):
    raw = re.sub(r"[\s().-]", "", value)
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if re.fullmatch(r"0[1-9]\d{8}", raw):
        raw = "+255" + raw[1:]
    elif re.fullmatch(r"255[1-9]\d{8}", raw):
        raw = "+" + raw
    if not re.fullmatch(r"\+[1-9]\d{7,14}", raw):
        raise serializers.ValidationError("Enter a valid phone number.")
    return raw


class ProviderCodeVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64, trim_whitespace=True, allow_blank=True)
    phone = serializers.CharField(max_length=32, trim_whitespace=True)

    def validate_phone(self, value):
        return normalize_phone(value)


class LocationSubmissionSerializer(serializers.Serializer):
    customerName = serializers.CharField(max_length=160, trim_whitespace=True)
    businessName = serializers.CharField(max_length=200, trim_whitespace=True)
    phone = serializers.CharField(max_length=32, trim_whitespace=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, min_value=-180, max_value=180
    )
    accuracyMeters = serializers.DecimalField(
        max_digits=9, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    locationSource = serializers.ChoiceField(
        choices=("gps", "manual_pin"), required=False
    )
    fixTimestamp = serializers.DateTimeField(required=False, allow_null=True)
    pinOffsetMeters = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    pinMovedByHand = serializers.BooleanField(required=False, default=False)
    consent = serializers.BooleanField()
    confirmed = serializers.BooleanField()
    publicListing = serializers.BooleanField()

    def validate_customerName(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Enter your full name.")
        return value

    def validate_businessName(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Enter your business name.")
        return value

    def validate_phone(self, value):
        return normalize_phone(value)

    def validate(self, attrs):
        if attrs["consent"] is not True or attrs["confirmed"] is not True:
            raise serializers.ValidationError("Consent and location confirmation are required.")
        lat, lng = attrs["latitude"], attrs["longitude"]
        if not (
            Decimal(str(settings.SERVICE_REGION_MIN_LAT))
            <= lat
            <= Decimal(str(settings.SERVICE_REGION_MAX_LAT))
        ) or not (
            Decimal(str(settings.SERVICE_REGION_MIN_LNG))
            <= lng
            <= Decimal(str(settings.SERVICE_REGION_MAX_LNG))
        ):
            raise serializers.ValidationError(
                {"latitude": "The selected location is outside the configured service area."}
            )

        fix_timestamp = attrs.get("fixTimestamp")
        source = attrs.get("locationSource") or ("gps" if fix_timestamp else "manual_pin")
        accuracy = attrs.get("accuracyMeters")
        if accuracy is not None and accuracy > Decimal(str(settings.LOCATION_MAX_ACCURACY_M)):
            raise serializers.ValidationError(
                {"accuracyMeters": "Reported GPS accuracy is outside the accepted range."}
            )
        if source == "gps" and (accuracy is None or fix_timestamp is None):
            raise serializers.ValidationError(
                {"fixTimestamp": "A GPS location requires its reported accuracy and fix time."}
            )
        fix_age_seconds = None
        if fix_timestamp is not None:
            raw_timestamp = (
                self.initial_data.get("fixTimestamp")
                if isinstance(self.initial_data, dict)
                else None
            )
            parsed_raw_timestamp = (
                parse_datetime(raw_timestamp) if isinstance(raw_timestamp, str) else None
            )
            if parsed_raw_timestamp is None or timezone.is_naive(parsed_raw_timestamp):
                raise serializers.ValidationError(
                    {"fixTimestamp": "The GPS fix time must include a timezone."}
                )
            now = timezone.now()
            if timezone.is_naive(fix_timestamp):
                raise serializers.ValidationError(
                    {"fixTimestamp": "The GPS fix time must include a timezone."}
                )
            age = (now - fix_timestamp).total_seconds()
            if age < -settings.LOCATION_FUTURE_SKEW_SECONDS:
                raise serializers.ValidationError(
                    {"fixTimestamp": "The GPS fix time is in the future."}
                )
            if age > settings.LOCATION_MAX_FIX_AGE_SECONDS:
                raise serializers.ValidationError(
                    {"fixTimestamp": "The GPS fix is too old. Retry location capture."}
                )
            fix_age_seconds = max(0, int(age))

        offset = attrs.get("pinOffsetMeters")
        if fix_timestamp is not None and attrs.get("pinMovedByHand") and offset is None:
            raise serializers.ValidationError(
                {"pinOffsetMeters": "Include the distance from the original GPS fix to the pin."}
            )
        attrs["locationSource"] = source
        attrs["pinOffsetMeters"] = offset
        attrs["fixAgeSeconds"] = fix_age_seconds
        attrs.pop("fixTimestamp", None)
        return attrs
