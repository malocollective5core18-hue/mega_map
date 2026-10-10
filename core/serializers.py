import re

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
        return attrs
