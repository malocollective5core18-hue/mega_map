import csv
import base64
import hashlib
import hmac
import io
import math
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Prefetch, Q
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django_otp.plugins.otp_totp.models import TOTPDevice
import qrcode
from qrcode.image.svg import SvgPathImage
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    AuditLog,
    BusinessLocation,
    CustomerBusiness,
    CustomerFlagCase,
    DemandCell,
    IdempotencyRecord,
    ProviderCode,
    ServiceVisit,
    StaffMFAFailure,
    StaffMFARecoveryCode,
    VerificationSession,
)
from .mfa import (
    clear_mfa_failures,
    consume_recovery_code,
    current_staff_device,
    establish_verified_session,
    is_mfa_exempt,
    is_mfa_verified,
    is_staff_user,
    mfa_locked,
    pending_mfa_user,
    record_mfa_failure,
    issue_recovery_codes,
)
from .permissions import AuditIsAuthenticated
from .security import (
    code_attempts_throttled,
    hash_value,
    issue_provider_code,
    record_audit,
    verify_provider_code,
)
from .serializers import LocationSubmissionSerializer, ProviderCodeVerifySerializer, normalize_phone
from .services import (
    acquire_submission_locks,
    find_duplicate,
    geometry_bounds,
    record_submission,
    rounded_public_coordinate,
)
from .throttles import PublicThrottle, StaffLoginThrottle, SubmissionThrottle, VerifyThrottle


def error(code, message, http_status):
    return Response({"error": {"code": code, "message": message}}, status=http_status)


def parse_bbox(raw):
    try:
        values = [float(v) for v in raw.split(",")]
        if len(values) != 4:
            raise ValueError
        west, south, east, north = values
        if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError
        if west > east:
            raise ValueError
        return west, south, east, north
    except AttributeError, TypeError, ValueError:
        raise ValueError("Invalid bbox. Use west,south,east,north in decimal degrees.")


def public_businesses_in_bbox(bbox):
    west, south, east, north = bbox
    return CustomerBusiness.objects.filter(
        status=CustomerBusiness.Status.SERVED,
        consent__public_listing=True,
        location__latitude__gte=south,
        location__latitude__lte=north,
        location__longitude__gte=west,
        location__longitude__lte=east,
    ).select_related("location", "consent")


def serialize_public_shop(business):
    location = business.location
    area = ", ".join(part for part in (location.ward, location.district, location.region) if part)
    return {
        "id": business.public_ref,
        "name": business.business_name,
        "area": area,
        "lat": rounded_public_coordinate(location.latitude),
        "lng": rounded_public_coordinate(location.longitude),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_shops(request):
    try:
        bbox = parse_bbox(request.data.get("bbox"))
    except ValueError as exc:
        return error("invalid_bbox", str(exc), status.HTTP_400_BAD_REQUEST)
    try:
        limit = min(500, max(1, int(request.data.get("limit", "500"))))
    except ValueError:
        return error(
            "invalid_limit",
            "Limit must be a whole number from 1 to 500.",
            status.HTTP_400_BAD_REQUEST,
        )
    rows = public_businesses_in_bbox(bbox).order_by("public_ref")[:limit]
    return Response({"items": [serialize_public_shop(row) for row in rows]})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_shop_search(request):
    query = str(request.data.get("q", "")).strip()
    if len(query) < 2 or len(query) > 100:
        return error(
            "invalid_query",
            "Search text must contain 2 to 100 characters.",
            status.HTTP_400_BAD_REQUEST,
        )
    businesses = (
        CustomerBusiness.objects.filter(
            status=CustomerBusiness.Status.SERVED,
            consent__public_listing=True,
            business_name__icontains=query,
        )
        .select_related("location", "consent")
        .order_by("business_name")[:20]
    )
    return Response({"items": [serialize_public_shop(row) for row in businesses]})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_demand_cells(request):
    try:
        bbox = parse_bbox(request.data.get("bbox"))
    except ValueError as exc:
        return error("invalid_bbox", str(exc), status.HTTP_400_BAD_REQUEST)
    west, south, east, north = bbox
    items = []
    # GeoJSON extents are stored in JSON because the chosen v1 schema avoids PostGIS.
    for cell in DemandCell.objects.filter(request_count__gte=3).iterator():
        bounds = geometry_bounds(cell.geojson)
        if not bounds:
            continue
        cell_w, cell_s, cell_e, cell_n = bounds
        if cell_e < west or cell_w > east or cell_n < south or cell_s > north:
            continue
        items.append({"cellId": cell.cell_id, "geojson": cell.geojson, "level": cell.level})
    return Response({"items": items})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_config(request):
    return Response(
        {
            "whatsappUrl": getattr(settings, "COMPANY_WHATSAPP_URL", ""),
            "phoneNumber": getattr(settings, "COMPANY_PHONE_NUMBER", ""),
            "privacyNoticeVersion": settings.PRIVACY_NOTICE_VERSION,
            "locationWarningAccuracyM": settings.LOCATION_WARN_ACCURACY_M,
            "locationMovingSpeedMps": settings.LOCATION_MOVING_SPEED_MPS,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([VerifyThrottle])
def verify_code(request):
    serializer = ProviderCodeVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"valid": False})
    raw_code = serializer.validated_data["code"]
    phone = serializer.validated_data["phone"]
    if code_attempts_throttled(raw_code):
        return error(
            "rate_limited",
            "Too many attempts. Wait and try again.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    token = verify_provider_code(raw_code, phone, request=request)
    if token == "ambiguous_business":
        return error(
            "ambiguous_legacy_key",
            "This older key is not linked to one business. Contact the company for a separate key for this business.",
            status.HTTP_409_CONFLICT,
        )
    if token is None:
        return Response({"valid": False})
    session = VerificationSession.objects.get(token_hash=hashlib.sha256(token.encode()).hexdigest())
    result = {
        "valid": True,
        "verificationToken": token,
        "expiresAt": session.expires_at.isoformat(),
    }
    if session.provider_code.reusable:
        customer = (
            CustomerBusiness.objects.select_related("location", "consent")
            .filter(pk=session.provider_code.business_id, phone=phone)
            .first()
        )
        if customer is not None:
            result["existingCustomer"] = {
                "reference": customer.public_ref,
                "customerName": customer.customer_name,
                "businessName": customer.business_name,
                "phone": customer.phone,
                "status": customer.status,
                "latitude": float(customer.location.navigation_latitude),
                "longitude": float(customer.location.navigation_longitude),
                "accuracyMeters": float(customer.location.accuracy_m)
                if customer.location.accuracy_m is not None
                else None,
                "publicListing": customer.consent.public_listing,
            }
            record_audit(
                request=request,
                actor=None,
                action="customer.key_login",
                object_type="CustomerBusiness",
                object_id=customer.pk,
            )
        else:
            record_audit(
                request=request,
                actor=None,
                action="customer.key_verified",
                object_type="ProviderCode",
                object_id=session.provider_code_id,
            )
    else:
        record_audit(
            request=request,
            actor=None,
            action="customer.key_verified",
            object_type="ProviderCode",
            object_id=session.provider_code_id,
        )
    return Response(result)


def bearer_token(request):
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([SubmissionThrottle])
def submit_location(request):
    serializer = LocationSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "error": {
                    "code": "invalid_submission",
                    "message": "Check the submitted details, consent, and location confirmation.",
                    "details": serializer.errors,
                }
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    token = bearer_token(request)
    if not token:
        return error(
            "verification_required",
            "Verify your provider code and try again.",
            status.HTTP_401_UNAUTHORIZED,
        )
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not 16 <= len(idempotency_key) <= 128:
        return error(
            "idempotency_key_required",
            "Send a valid Idempotency-Key with this submission.",
            status.HTTP_400_BAD_REQUEST,
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    key_hash = hash_value(idempotency_key)
    try:
        with transaction.atomic():
            session = (
                VerificationSession.objects.select_for_update()
                .select_related("provider_code")
                .filter(token_hash=token_hash)
                .first()
            )
            if session is None:
                return error(
                    "verification_expired",
                    "Your verification session is invalid or expired. Start again.",
                    status.HTTP_410_GONE,
                )
            prior = IdempotencyRecord.objects.filter(key_hash=key_hash).first()
            if prior:
                if prior.session_id != session.pk:
                    return error(
                        "idempotency_conflict",
                        "This request key has already been used.",
                        status.HTTP_409_CONFLICT,
                    )
                return Response(prior.response_body, status=prior.response_status)
            if session.expires_at <= timezone.now() or session.used_at is not None:
                return error(
                    "verification_expired",
                    "Your verification session is invalid or expired. Start again.",
                    status.HTTP_410_GONE,
                )
            data = serializer.validated_data
            provider_code = ProviderCode.objects.select_for_update().get(pk=session.provider_code_id)
            expected_phone_hash = provider_code.target_phone_hash
            if not expected_phone_hash or not hmac.compare_digest(
                expected_phone_hash, hash_value("provider-phone:" + data["phone"])
            ):
                return error(
                    "phone_code_mismatch",
                    "Use the phone number associated with this service code.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if provider_code.business_id is not None:
                return error(
                    "customer_key_already_linked",
                    "This key belongs to an existing business account. Sign in to update that account.",
                    status.HTTP_409_CONFLICT,
                )
            acquire_submission_locks(
                phone=data["phone"], latitude=data["latitude"], longitude=data["longitude"]
            )
            if find_duplicate(
                phone=data["phone"],
                business_name=data["businessName"],
                latitude=data["latitude"],
                longitude=data["longitude"],
            ):
                body = {
                    "error": {
                        "code": "duplicate",
                        "message": "A request for this location already exists.",
                    }
                }
                record_audit(
                    request=request,
                    action="customer.submission_rejected",
                    object_type="Submission",
                    object_id="duplicate-location",
                    metadata={"status": 409, "error_code": "duplicate"},
                )
                IdempotencyRecord.objects.create(
                    key_hash=key_hash, session=session, response_status=409, response_body=body
                )
                return Response(body, status=status.HTTP_409_CONFLICT)
            business = record_submission(data=data, request=request)
            provider_code.business = business
            provider_code.legacy_phone_lookup = False
            provider_code.save(update_fields=["business", "legacy_phone_lookup"])
            body = {
                "accepted": True,
                "reference": business.public_ref,
                "status": business.status,
            }
            session.used_at = timezone.now()
            session.save(update_fields=["used_at"])
            IdempotencyRecord.objects.create(
                key_hash=key_hash,
                session=session,
                business=business,
                response_status=status.HTTP_201_CREATED,
                response_body=body,
            )
            return Response(body, status=status.HTTP_201_CREATED)
    except IntegrityError:
        prior = IdempotencyRecord.objects.filter(key_hash=key_hash).first()
        if prior and prior.session_id == getattr(locals().get("session"), "pk", None):
            return Response(prior.response_body, status=prior.response_status)
        return error(
            "idempotency_conflict",
            "This request key has already been used.",
            status.HTTP_409_CONFLICT,
        )


@api_view(["PUT"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([SubmissionThrottle])
def update_customer_profile(request):
    serializer = LocationSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "error": {
                    "code": "invalid_submission",
                    "message": "Check the submitted details, consent, and location confirmation.",
                    "details": serializer.errors,
                }
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    token = bearer_token(request)
    if not token:
        return error(
            "customer_login_required",
            "Sign in with your phone and customer key, then try again.",
            status.HTTP_401_UNAUTHORIZED,
        )
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not 16 <= len(idempotency_key) <= 128:
        return error(
            "idempotency_key_required",
            "Send a valid Idempotency-Key with this update.",
            status.HTTP_400_BAD_REQUEST,
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    key_hash = hash_value(idempotency_key)
    try:
        with transaction.atomic():
            session = (
                VerificationSession.objects.select_for_update()
                .select_related("provider_code")
                .filter(token_hash=token_hash)
                .first()
            )
            if session is None:
                return error(
                    "verification_expired",
                    "Your customer login expired. Sign in again with your key.",
                    status.HTTP_410_GONE,
                )
            prior = IdempotencyRecord.objects.filter(key_hash=key_hash).first()
            if prior:
                if prior.session_id != session.pk:
                    return error(
                        "idempotency_conflict",
                        "This request key has already been used.",
                        status.HTTP_409_CONFLICT,
                    )
                return Response(prior.response_body, status=prior.response_status)
            if session.expires_at <= timezone.now() or session.used_at is not None:
                return error(
                    "verification_expired",
                    "Your customer login expired. Sign in again with your key.",
                    status.HTTP_410_GONE,
                )
            if not session.provider_code.reusable:
                return error(
                    "customer_login_required",
                    "This code is for one-time registration. Sign in with a reusable customer key "
                    "to update your account.",
                    status.HTTP_403_FORBIDDEN,
                )
            data = serializer.validated_data
            expected_phone_hash = session.provider_code.target_phone_hash
            if not expected_phone_hash or not hmac.compare_digest(
                expected_phone_hash, hash_value("provider-phone:" + data["phone"])
            ):
                return error(
                    "phone_code_mismatch",
                    "Use the phone number associated with your customer key.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            business = (
                CustomerBusiness.objects.select_related("location", "consent")
                .filter(pk=session.provider_code.business_id, phone=data["phone"])
                .first()
            )
            if business is None:
                return error(
                    "customer_not_found",
                    "No registered customer account was found for this phone. Use Register to "
                    "submit your business details first.",
                    status.HTTP_404_NOT_FOUND,
                )

            business.customer_name = data["customerName"]
            business.business_name = data["businessName"]
            business.location.latitude = data["latitude"]
            business.location.longitude = data["longitude"]
            business.location.accuracy_m = data.get("accuracyMeters")
            business.location.source = data.get(
                "locationSource", BusinessLocation.Source.MANUAL
            )
            business.location.fix_age_seconds = data.get("fixAgeSeconds")
            business.location.pin_offset_m = data.get("pinOffsetMeters")
            business.location.pin_moved_by_hand = data.get("pinMovedByHand", False)
            business.location.captured_at = timezone.now()
            business.location.corrected_lat = None
            business.location.corrected_lng = None
            business.location.corrected_by = None
            business.location.corrected_at = None
            business.location.team_verified = False
            business.consent.public_listing = data["publicListing"]
            business.consent.privacy_notice_version = settings.PRIVACY_NOTICE_VERSION
            business.consent.given_at = timezone.now()
            business.consent.ip_hash = hash_value(request.META.get("REMOTE_ADDR", ""))
            business.location.save(
                update_fields=[
                    "latitude",
                    "longitude",
                    "accuracy_m",
                    "source",
                    "fix_age_seconds",
                    "pin_offset_m",
                    "pin_moved_by_hand",
                    "captured_at",
                    "corrected_lat",
                    "corrected_lng",
                    "corrected_by",
                    "corrected_at",
                    "team_verified",
                ]
            )
            business.consent.save(
                update_fields=["public_listing", "privacy_notice_version", "given_at", "ip_hash"]
            )
            business.save(update_fields=["customer_name", "business_name", "updated_at"])
            session.used_at = timezone.now()
            session.save(update_fields=["used_at"])
            body = {
                "updated": True,
                "reference": business.public_ref,
                "status": business.status,
            }
            IdempotencyRecord.objects.create(
                key_hash=key_hash,
                session=session,
                business=business,
                response_status=status.HTTP_200_OK,
                response_body=body,
            )
            record_audit(
                request=request,
                actor=None,
                action="customer.profile_updated",
                object_type="CustomerBusiness",
                object_id=business.pk,
                metadata={
                    "changed_fields": [
                        "customer_name",
                        "business_name",
                        "location",
                        "public_listing",
                    ]
                },
            )
            return Response(body)
    except IntegrityError:
        prior = IdempotencyRecord.objects.filter(key_hash=key_hash).first()
        if prior and prior.session_id == getattr(locals().get("session"), "pk", None):
            return Response(prior.response_body, status=prior.response_status)
        return error(
            "idempotency_conflict",
            "This request key has already been used.",
            status.HTTP_409_CONFLICT,
        )


def has_role(user, role):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=role).exists())


def staff_required(request, *, admin=False):
    role = "admin" if admin else None
    if not request.user.is_authenticated:
        record_audit(
            request=request,
            actor=None,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "anonymous"},
        )
        return error(
            "not_authenticated", "Staff sign-in is required.", status.HTTP_401_UNAUTHORIZED
        )
    if role and not has_role(request.user, role):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "role_required"},
        )
        return error(
            "admin_role_required",
            "This action is limited to administrators.",
            status.HTTP_403_FORBIDDEN,
        )
    if not role and not (
        has_role(request.user, "dispatcher")
        or has_role(request.user, "admin")
        or has_role(request.user, "field_team")
    ):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "staff_role_required"},
        )
        return error(
            "staff_role_required", "This action is limited to staff.", status.HTTP_403_FORBIDDEN
        )
    return None


def service_provider_or_superuser(user):
    return user.is_superuser or user.groups.filter(name="service_provider").exists()


def admin_or_superuser(user):
    return user.is_superuser or user.groups.filter(name="admin").exists()


def superuser_required(request):
    if not request.user.is_superuser:
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "superuser_required"},
        )
        return error(
            "superuser_required",
            "Only the superuser can manage staff accounts.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


@api_view(["GET"])
@permission_classes([AllowAny])
def auth_csrf(request):
    return Response({"csrfToken": get_token(request._request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([StaffLoginThrottle])
def auth_login(request):
    raw_request = request._request
    csrf_failure = CsrfViewMiddleware(lambda req: HttpResponse()).process_view(
        raw_request, lambda req: None, (), {}
    )
    if csrf_failure is not None:
        record_audit(
            request=request,
            actor=None,
            action="auth.login_failed",
            object_type="User",
            metadata={"reason": "csrf"},
        )
        return error(
            "csrf_failed", "Refresh the sign-in page and try again.", status.HTTP_403_FORBIDDEN
        )
    raw_email = request.data.get("email", "")
    password = request.data.get("password", "")
    if not isinstance(raw_email, str) or not isinstance(password, str):
        return error(
            "invalid_credentials", "Email or password is incorrect.", status.HTTP_401_UNAUTHORIZED
        )
    email = raw_email.strip()
    matching_users = (
        get_user_model().objects.filter(email__iexact=email).order_by("pk")[:2] if email else []
    )
    matches = list(matching_users)
    user = (
        authenticate(request=raw_request, username=matches[0].get_username(), password=password)
        if len(matches) == 1
        else None
    )
    if (
        user is None
        or not user.is_active
        or not (
            has_role(user, "dispatcher")
            or has_role(user, "admin")
            or user.groups.filter(name="service_provider").exists()
            or user.groups.filter(name="field_team").exists()
        )
    ):
        record_audit(
            request=request,
            actor=None,
            action="auth.login_failed",
            object_type="User",
            metadata={"reason": "credentials_or_role"},
        )
        return error(
            "invalid_credentials", "Email or password is incorrect.", status.HTTP_401_UNAUTHORIZED
        )
    if user.is_superuser:
        role = "superuser"
    elif user.groups.filter(name="admin").exists():
        role = "admin"
    elif user.groups.filter(name="service_provider").exists():
        role = "service_provider"
    elif user.groups.filter(name="field_team").exists():
        role = "field_team"
    else:
        role = "dispatcher"

    if is_mfa_exempt(user):
        login(raw_request, user)
        raw_request.session["mfa_verified_user_id"] = str(user.pk)
        raw_request.session.pop("mfa_pending_user_id", None)
        raw_request.session.pop("mfa_pending_expires_at", None)
        return Response({"authenticated": True, "role": role})

    if current_staff_device(user, confirmed=True):
        logout(raw_request)
        raw_request.session["mfa_pending_user_id"] = user.pk
        raw_request.session["mfa_pending_expires_at"] = (
            timezone.now().timestamp() + settings.MFA_CHALLENGE_SECONDS
        )
        raw_request.session.set_expiry(settings.MFA_CHALLENGE_SECONDS)
        return Response({"authenticated": False, "mfaRequired": True})

    login(raw_request, user)
    raw_request.session.pop("mfa_verified_user_id", None)
    return Response({"authenticated": False, "mfaEnrollmentRequired": True, "role": role})


def mfa_csrf_valid(request):
    raw_request = request._request
    failure = CsrfViewMiddleware(lambda req: HttpResponse()).process_view(
        raw_request, lambda req: None, (), {}
    )
    return failure is None


def mfa_error():
    return error(
        "invalid_mfa", "The verification details could not be accepted. Try again.", 401
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([StaffLoginThrottle])
def auth_mfa_verify(request):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    user = pending_mfa_user(request)
    token = request.data.get("code", "")
    if user is None or not isinstance(token, str) or mfa_locked(user):
        return mfa_error()
    device = current_staff_device(user, confirmed=True)
    if device is None or not device.verify_token(token.strip()):
        record_mfa_failure(request, user, "totp_invalid")
        return mfa_error()
    establish_verified_session(request, user, method="totp")
    return Response({"authenticated": True})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([StaffLoginThrottle])
def auth_mfa_recovery(request):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    user = pending_mfa_user(request)
    if user is None or mfa_locked(user):
        return mfa_error()
    with transaction.atomic():
        if not consume_recovery_code(user, request.data.get("code", "")):
            record_mfa_failure(request, user, "recovery_invalid")
            return mfa_error()
    establish_verified_session(request, user, method="recovery")
    return Response({"authenticated": True})


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def auth_mfa_enroll(request):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    user = request.user
    if not is_staff_user(user) or current_staff_device(user, confirmed=True):
        return error("mfa_enrollment_unavailable", "Staff MFA enrollment is unavailable.", 403)
    device = current_staff_device(user, confirmed=False)
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Authenticator", confirmed=False)
    provisioning_uri = device.config_url
    qr = qrcode.make(provisioning_uri, image_factory=SvgPathImage)
    qr_file = io.BytesIO()
    qr.save(qr_file)
    qr_data = base64.b64encode(qr_file.getvalue()).decode("ascii")
    secret = base64.b32encode(device.bin_key).decode("ascii").rstrip("=")
    return Response(
        {
            "secret": secret,
            "otpauthUrl": provisioning_uri,
            "qrSvg": "data:image/svg+xml;base64," + qr_data,
        }
    )


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def auth_mfa_confirm(request):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    user = request.user
    if not is_staff_user(user) or current_staff_device(user, confirmed=True):
        return error("mfa_enrollment_unavailable", "Staff MFA enrollment is unavailable.", 403)
    device = current_staff_device(user, confirmed=False)
    token = request.data.get("code", "")
    if device is None or not isinstance(token, str) or mfa_locked(user):
        return mfa_error()
    if not device.verify_token(token.strip()):
        record_mfa_failure(request, user, "enrollment_totp_invalid")
        return mfa_error()
    device.confirmed = True
    device.save(update_fields=["confirmed"])
    codes = issue_recovery_codes(user)
    establish_verified_session(request, user, method="enrollment")
    record_audit(
        request=request,
        actor=user,
        action="auth.mfa_enrolled",
        object_type="User",
        object_id=user.pk,
    )
    return Response({"authenticated": True, "recoveryCodes": codes})


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def auth_mfa_regenerate_recovery(request):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    user = request.user
    device = current_staff_device(user, confirmed=True)
    token = request.data.get("code", "")
    if not is_staff_user(user) or not is_mfa_verified(request) or device is None:
        return error("mfa_required", "Verified staff sign-in is required.", 403)
    if not isinstance(token, str) or not device.verify_token(token.strip()):
        record_mfa_failure(request, user, "recovery_regeneration_totp_invalid")
        return mfa_error()
    codes = issue_recovery_codes(user)
    record_audit(
        request=request,
        actor=user,
        action="auth.mfa_recovery_regenerated",
        object_type="User",
        object_id=user.pk,
    )
    return Response({"recoveryCodes": codes})


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_mfa_reenroll(request, user_id):
    if not mfa_csrf_valid(request):
        return error("csrf_failed", "Refresh the sign-in page and try again.", 403)
    owner_email = settings.MFA_RECOVERY_OWNER_EMAIL
    if (
        not owner_email
        or not request.user.is_superuser
        or not is_mfa_verified(request)
        or request.user.email.strip().lower() != owner_email
    ):
        return error("mfa_recovery_owner_required", "The configured MFA recovery owner must approve this action.", 403)
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or not is_staff_user(user):
        return error("not_found", "Staff account not found.", 404)
    TOTPDevice.objects.filter(user=user).delete()
    StaffMFARecoveryCode.objects.filter(user=user).delete()
    StaffMFAFailure.objects.filter(user=user).delete()
    record_audit(
        request=request,
        actor=request.user,
        action="auth.mfa_reenrolled_by_owner",
        object_type="User",
        object_id=user.pk,
        metadata={"owner_id": request.user.pk},
    )
    return Response({"mfaEnrollmentRequired": True})


@api_view(["GET", "POST"])
@permission_classes([AuditIsAuthenticated])
def admin_staff_users(request):
    denied = superuser_required(request)
    if denied:
        return denied

    User = get_user_model()
    if request.method == "GET":
        users = (
            User.objects.filter(groups__name__in=["admin", "service_provider", "field_team"])
            .distinct()
            .order_by("username")
        )
        items = [
            {
                "id": user.pk,
                "username": user.get_username(),
                "email": user.email,
                "role": next(
                    (
                        role
                        for role in ("service_provider", "field_team", "admin")
                        if user.groups.filter(name=role).exists()
                    ),
                    "admin",
                ),
                "active": user.is_active,
                "createdAt": user.date_joined.isoformat(),
            }
            for user in users
        ]
        record_audit(
            request=request,
            actor=request.user,
            action="staff.users_listed",
            object_type="User",
            object_id="all",
        )
        return Response({"items": items})

    username = request.data.get("username", "")
    email = request.data.get("email", "")
    password = request.data.get("password", "")
    role = request.data.get("role", "")
    if not all(isinstance(value, str) for value in (username, email, password, role)):
        return error(
            "invalid_staff_user",
            "Enter a username, email, password, and role.",
            status.HTTP_400_BAD_REQUEST,
        )
    username, email, role = username.strip(), email.strip(), role.strip()
    if (
        not username
        or len(username) > 150
        or not email
        or len(email) > 254
        or not password
        or role not in ("admin", "service_provider", "field_team")
    ):
        return error(
            "invalid_staff_user",
            "Enter a valid username, email, password, and allowed staff role.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        User._meta.get_field(User.USERNAME_FIELD).clean(username, None)
        User._meta.get_field("email").clean(email, None)
        validate_password(password)
    except Exception as exc:
        from django.core.exceptions import ValidationError as DjangoValidationError

        if isinstance(exc, DjangoValidationError):
            return error("invalid_staff_user", " ".join(exc.messages), status.HTTP_400_BAD_REQUEST)
        raise
    if User.objects.filter(**{User.USERNAME_FIELD: username}).exists():
        return error(
            "username_exists", "That username is already in use.", status.HTTP_409_CONFLICT
        )
    if User.objects.filter(email__iexact=email).exists():
        return error(
            "email_exists",
            "That email address is already assigned to a staff account.",
            status.HTTP_409_CONFLICT,
        )
    from django.contrib.auth.models import Group

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                **{User.USERNAME_FIELD: username, "email": email, "password": password}
            )
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
            record_audit(
                request=request,
                actor=request.user,
                action="staff.user_created",
                object_type="User",
                object_id=user.pk,
            )
    except IntegrityError:
        return error(
            "username_exists", "That username is already in use.", status.HTTP_409_CONFLICT
        )
    return Response(
        {"id": user.pk, "username": user.get_username(), "email": user.email, "role": role},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def auth_logout(request):
    record_audit(
        request=request,
        actor=request.user,
        action="auth.logout",
        object_type="User",
        object_id=request.user.pk,
    )
    logout(request._request)
    return Response({"authenticated": False})


def current_location_filter(queryset, bbox):
    west, south, east, north = bbox
    return queryset.filter(
        Q(
            location__latitude__gte=south,
            location__latitude__lte=north,
            location__longitude__gte=west,
            location__longitude__lte=east,
        )
        | Q(
            location__team_verified=True,
            location__corrected_lat__gte=south,
            location__corrected_lat__lte=north,
            location__corrected_lng__gte=west,
            location__corrected_lng__lte=east,
        )
    )


def navigation_links(location):
    lat, lng = location.navigation_latitude, location.navigation_longitude
    if lat is None or lng is None:
        return None
    try:
        lat = Decimal(lat).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        lng = Decimal(lng).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except InvalidOperation, TypeError, ValueError:
        return None
    if not lat.is_finite() or not lng.is_finite() or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        return None
    lat_text, lng_text = f"{lat:.6f}", f"{lng:.6f}"
    pair = f"{lat_text},{lng_text}"
    google_driving = (
        f"https://www.google.com/maps/dir/?api=1&destination={quote(pair, safe=',')}"
        "&travelmode=driving"
    )
    google_walking = (
        f"https://www.google.com/maps/dir/?api=1&destination={quote(pair, safe=',')}"
        "&travelmode=walking"
    )
    return {
        "googleMaps": google_driving,
        "googleMapsDriving": google_driving,
        "googleMapsWalking": google_walking,
        "waze": f"https://waze.com/ul?ll={quote(pair, safe=',')}&navigate=yes",
        "appleMaps": f"https://maps.apple.com/?daddr={quote(pair, safe=',')}",
        "openStreetMap": (
            f"https://www.openstreetmap.org/?mlat={lat_text}&mlon={lng_text}"
            f"#map=19/{lat_text}/{lng_text}"
        ),
        "whatsappShare": f"https://wa.me/?text={quote(google_driving, safe='')}",
    }


def location_confidence(location):
    if location.team_verified:
        return {"level": "high", "message": "A staff member has checked this pin on site."}
    if location.accuracy_m is None or location.fix_age_seconds is None:
        return {"level": "low", "message": "Call the customer to confirm before travelling."}
    accuracy = float(location.accuracy_m)
    age = int(location.fix_age_seconds)
    offset = float(location.pin_offset_m) if location.pin_offset_m is not None else None
    if offset is not None and offset > settings.LOCATION_LARGE_OFFSET_M:
        return {
            "level": "low",
            "message": (
                "The pin offset from its GPS estimate is large. "
                "Call the customer to confirm."
            ),
        }
    if age > settings.LOCATION_MAX_FIX_AGE_SECONDS:
        return {
            "level": "low",
            "message": "The location reading is old. Call the customer to confirm.",
        }
    if location.source == BusinessLocation.Source.MANUAL and offset is None:
        return {
            "level": "low",
            "message": "This pin was placed manually. Call the customer to confirm.",
        }
    if (
        location.source == BusinessLocation.Source.GPS
        and accuracy <= 30
        and age <= 30
        and offset is not None
        and offset <= 50
    ):
        return {"level": "high", "message": ""}
    if accuracy <= 100 and offset is not None and offset <= settings.LOCATION_LARGE_OFFSET_M:
        return {
            "level": "medium",
            "message": "Check the pin and allow extra time to confirm the entrance.",
        }
    return {"level": "low", "message": "Call the customer to confirm before travelling."}


def phone_access(business, *, codes=None, phone_count=None, legacy_codes=None):
    if codes is None:
        codes = ProviderCode.objects.filter(business=business)
        if not codes.exists() and CustomerBusiness.objects.filter(phone=business.phone).count() == 1:
            codes = ProviderCode.objects.filter(
                business__isnull=True,
                legacy_phone_lookup=True,
                target_phone_hash=hash_value("provider-phone:" + business.phone),
            )
    else:
        codes = list(codes)
        if not codes and phone_count == 1:
            codes = list(legacy_codes or [])
    now = timezone.now()
    if isinstance(codes, list):
        active_codes = [
            code
            for code in codes
            if code.status == ProviderCode.Status.ACTIVE
            and code.expires_at > now
            and (code.reusable or code.use_count < code.max_uses)
        ]
        code = active_codes[0] if active_codes else None
    else:
        code = (
            codes.filter(status=ProviderCode.Status.ACTIVE, expires_at__gt=now)
            .filter(Q(reusable=True) | Q(use_count__lt=F("max_uses")))
            .order_by("-created_at")
            .first()
        )
    if code is not None:
        return {"status": "active", "expiresAt": code.expires_at.isoformat()}
    if isinstance(codes, list):
        code = codes[0] if codes else None
    else:
        code = codes.order_by("-created_at").first()
    if code is None:
        return {"status": "not_issued", "expiresAt": None}
    if code.status == ProviderCode.Status.REVOKED:
        state = "revoked"
    elif code.expires_at <= timezone.now():
        state = "expired"
    elif not code.reusable and code.use_count >= code.max_uses:
        state = "used"
    else:
        state = "active"
    return {"status": state, "expiresAt": code.expires_at.isoformat()}


def serialize_staff_business(
    business, *, detail=False, provider_codes=None, phone_count=None, legacy_codes=None
):
    location = business.location
    result = {
        "id": str(business.pk),
        "reference": business.public_ref,
        "businessName": business.business_name,
        "customerName": business.customer_name,
        "phone": business.phone,
        "accountAccess": phone_access(
            business, codes=provider_codes, phone_count=phone_count, legacy_codes=legacy_codes
        ),
        "status": business.status,
        "accuracyMeters": float(location.accuracy_m) if location.accuracy_m is not None else None,
        "locationSource": location.source,
        "fixAgeSeconds": location.fix_age_seconds,
        "pinOffsetMeters": float(location.pin_offset_m)
        if location.pin_offset_m is not None
        else None,
        "pinMovedByHand": location.pin_moved_by_hand,
        "latitude": float(location.navigation_latitude),
        "longitude": float(location.navigation_longitude),
        "locationConfidence": location_confidence(location),
        "navigationLinks": navigation_links(location),
        "teamVerified": location.team_verified,
        "publicListing": business.consent.public_listing,
        "createdAt": business.created_at.isoformat(),
        "updatedAt": business.updated_at.isoformat(),
        "assignedTo": business.assigned_to_id,
    }
    if detail:
        result.update(
            {
                "originalLatitude": float(location.latitude),
                "originalLongitude": float(location.longitude),
                "correctedLatitude": float(location.corrected_lat)
                if location.corrected_lat is not None
                else None,
                "correctedLongitude": float(location.corrected_lng)
                if location.corrected_lng is not None
                else None,
                "correctedAt": location.corrected_at.isoformat() if location.corrected_at else None,
                "correctedBy": location.corrected_by_id,
                "source": location.source,
                "capturedAt": location.captured_at.isoformat(),
                "address": location.address_text,
                "ward": location.ward,
                "district": location.district,
                "region": location.region,
                "notes": business.notes,
                "privacyNoticeVersion": business.consent.privacy_notice_version,
                "locationConsent": business.consent.location_processing,
                "visits": [
                    {
                        "date": visit.visit_date.isoformat(),
                        "team": visit.team,
                        "outcome": visit.outcome,
                    }
                    for visit in business.visits.all()
                ],
            }
        )
    return result


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_businesses(request):
    denied = staff_required(request)
    if denied:
        return denied
    businesses = CustomerBusiness.objects.select_related("location", "consent", "assigned_to")
    if has_role(request.user, "field_team") and not request.user.is_superuser:
        businesses = businesses.filter(assigned_to=request.user)
    status_filter = str(request.data.get("status", "")).strip()
    if status_filter:
        if status_filter not in CustomerBusiness.Status.values:
            return error("invalid_status", "Unknown business status.", status.HTTP_400_BAD_REQUEST)
        businesses = businesses.filter(status=status_filter)
    query = str(request.data.get("q", "")).strip()
    if query:
        search_filter = (
            Q(public_ref__icontains=query)
            | Q(business_name__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(phone__icontains=query)
        )
        phone_digits = "".join(char for char in query if char.isdigit())
        if phone_digits.startswith("00"):
            phone_digits = phone_digits[2:]
        if phone_digits.startswith("0"):
            phone_digits = "255" + phone_digits[1:]
        if phone_digits:
            search_filter |= Q(phone__icontains=phone_digits)
        businesses = businesses.filter(search_filter)
    bbox_arg = request.data.get("bbox")
    if bbox_arg:
        try:
            businesses = current_location_filter(businesses, parse_bbox(bbox_arg))
        except ValueError as exc:
            return error("invalid_bbox", str(exc), status.HTTP_400_BAD_REQUEST)
    try:
        page = max(1, int(request.data.get("page", "1")))
    except ValueError:
        return error("invalid_page", "Page must be a whole number.", status.HTTP_400_BAD_REQUEST)
    sort_order = str(request.data.get("sort", "recently_updated"))
    ordering = {
        "recently_updated": ("-updated_at", "-pk"),
        "newest_created": ("-created_at", "-pk"),
    }.get(sort_order)
    if ordering is None:
        return error("invalid_sort", "Choose a supported customer order.", status.HTTP_400_BAD_REQUEST)
    page_size = 50
    count = businesses.count()
    pages = max(1, math.ceil(count / page_size))
    page = min(page, pages)
    record_audit(
        request=request,
        actor=request.user,
        action="business.list_viewed",
        object_type="CustomerBusiness",
        object_id="",
    )
    rows = list(
        businesses.prefetch_related(
            Prefetch(
                "provider_codes",
                queryset=ProviderCode.objects.order_by("-created_at"),
                to_attr="staff_provider_codes",
            )
        )
        .order_by(*ordering)[(page - 1) * page_size : page * page_size]
    )
    phones = {row.phone for row in rows}
    phone_counts = {
        phone: total
        for phone, total in CustomerBusiness.objects.filter(phone__in=phones)
        .values_list("phone")
        .annotate(total=Count("pk"))
    }
    phone_hashes = {hash_value("provider-phone:" + phone) for phone in phones}
    legacy_codes_by_hash = {}
    if phone_hashes:
        for code in ProviderCode.objects.filter(
            business__isnull=True,
            legacy_phone_lookup=True,
            target_phone_hash__in=phone_hashes,
        ).order_by("-created_at"):
            legacy_codes_by_hash.setdefault(code.target_phone_hash, []).append(code)
    awaiting_submission = None
    if not has_role(request.user, "field_team") or request.user.is_superuser:
        awaiting_submission = (
            ProviderCode.objects.filter(
                business__isnull=True,
                status=ProviderCode.Status.ACTIVE,
                expires_at__gt=timezone.now(),
            )
            .filter(Q(reusable=True) | Q(use_count__lt=F("max_uses")))
            .count()
        )
    return Response(
        {
            "count": count,
            "page": page,
            "pages": pages,
            "awaitingSubmission": awaiting_submission,
            "items": [
                serialize_staff_business(
                    row,
                    provider_codes=row.staff_provider_codes,
                    phone_count=phone_counts.get(row.phone, 0),
                    legacy_codes=legacy_codes_by_hash.get(
                        hash_value("provider-phone:" + row.phone), []
                    ),
                )
                for row in rows
            ],
        }
    )


@api_view(["GET"])
@permission_classes([AuditIsAuthenticated])
def admin_assignable_staff(request):
    denied = staff_required(request)
    if denied:
        return denied
    if has_role(request.user, "field_team") and not request.user.is_superuser:
        return error("dispatcher_role_required", "Only dispatch staff can assign jobs.", 403)
    User = get_user_model()
    users = (
        User.objects.filter(is_active=True, groups__name__in=["dispatcher", "admin", "field_team"])
        .distinct()
        .order_by("username")
    )
    return Response(
        {
            "items": [
                {
                    "id": user.pk,
                    "username": user.get_username(),
                    "role": next(
                        (
                            role
                            for role in ("field_team", "dispatcher", "admin")
                            if user.groups.filter(name=role).exists()
                        ),
                        "staff",
                    ),
                }
                for user in users
            ]
        }
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AuditIsAuthenticated])
def admin_business_detail(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
    if request.method == "DELETE":
        denied = staff_required(request, admin=True)
        if denied:
            return denied
    business = (
        CustomerBusiness.objects.select_related("location", "consent", "assigned_to")
        .filter(pk=business_id)
        .first()
    )
    if business is None:
        return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
    is_field_team = has_role(request.user, "field_team") and not request.user.is_superuser
    if is_field_team and business.assigned_to_id != request.user.pk:
        return error("not_found", "Assigned business not found.", status.HTTP_404_NOT_FOUND)
    original_phone = business.phone
    if request.method == "GET":
        record_audit(
            request=request,
            actor=request.user,
            action="business.detail_viewed",
            object_type="CustomerBusiness",
            object_id=business.pk,
        )
        return Response(serialize_staff_business(business, detail=True))
    if request.method == "DELETE":
        with transaction.atomic():
            business = (
                CustomerBusiness.objects.select_for_update(of=("self",))
                .select_related("location")
                .filter(pk=business_id)
                .first()
            )
            if business is None:
                return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
            acquire_submission_locks(
                phone=business.phone,
                latitude=business.location.latitude,
                longitude=business.location.longitude,
            )
            phone_hash = hash_value("provider-phone:" + business.phone)
            code_ids = list(
                ProviderCode.objects.select_for_update()
                .filter(
                    Q(business=business)
                    | Q(
                        business__isnull=True,
                        legacy_phone_lookup=True,
                        target_phone_hash=phone_hash,
                    )
                )
                .values_list("pk", flat=True)
            )
            now = timezone.now()
            live_key_query = ProviderCode.objects.filter(
                pk__in=code_ids,
                status=ProviderCode.Status.ACTIVE,
                expires_at__gt=now,
            ).filter(Q(reusable=True) | Q(use_count__lt=F("max_uses")))
            revoked_key_count = live_key_query.count()
            VerificationSession.objects.filter(
                provider_code_id__in=code_ids, used_at__isnull=True
            ).update(used_at=now)
            ProviderCode.objects.filter(
                pk__in=code_ids, status=ProviderCode.Status.ACTIVE
            ).update(
                status=ProviderCode.Status.REVOKED,
                revoked_at=now,
            )
            ProviderCode.objects.filter(pk__in=code_ids).update(
                target_phone_hash="",
                target_phone_last4="",
            )
            IdempotencyRecord.objects.filter(business=business).delete()
            record_audit(
                request=request,
                actor=request.user,
                action="customer.deleted",
                object_type="CustomerBusiness",
                object_id=business.pk,
                metadata={
                    "reference": business.public_ref,
                    "revoked_key_count": revoked_key_count,
                    "keys_unlinked": len(code_ids),
                },
            )
            business.delete()
        return Response({"deleted": True, "revokedKeys": revoked_key_count})
    data = request.data
    allowed = {
        "customerName",
        "businessName",
        "phone",
        "status",
        "notes",
        "assignee",
        "publicListing",
        "correctedLatitude",
        "correctedLongitude",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        return error(
            "invalid_patch", "The update contains unsupported fields.", status.HTTP_400_BAD_REQUEST
        )
    if is_field_team and set(data) - {"correctedLatitude", "correctedLongitude"}:
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="CustomerBusiness",
            object_id=business.pk,
            metadata={"reason": "field_team_pin_only"},
        )
        return error(
            "field_team_pin_only", "Field team members may only correct an assigned location.", 403
        )
    if "publicListing" in data and not has_role(request.user, "admin"):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "admin_role_required"},
        )
        return error(
            "admin_role_required",
            "Only administrators can change public listing consent.",
            status.HTTP_403_FORBIDDEN,
        )
    if "status" in data:
        if data["status"] not in CustomerBusiness.Status.values:
            return error("invalid_status", "Unknown business status.", status.HTTP_400_BAD_REQUEST)
        business.status = data["status"]
    if "customerName" in data:
        if (
            not isinstance(data["customerName"], str)
            or not 2 <= len(data["customerName"].strip()) <= 160
        ):
            return error(
                "invalid_customer_name",
                "Customer name must be 2–160 characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        business.customer_name = data["customerName"].strip()
    if "businessName" in data:
        if (
            not isinstance(data["businessName"], str)
            or not 2 <= len(data["businessName"].strip()) <= 200
        ):
            return error(
                "invalid_business_name",
                "Business name must be 2–200 characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        business.business_name = data["businessName"].strip()
    if "phone" in data:
        try:
            business.phone = (
                normalize_phone(data["phone"]) if isinstance(data["phone"], str) else ""
            )
        except ValidationError:
            return error(
                "invalid_phone", "Enter a valid phone number.", status.HTTP_400_BAD_REQUEST
            )
    if "notes" in data:
        if not isinstance(data["notes"], str) or len(data["notes"]) > 10000:
            return error(
                "invalid_notes",
                "Notes must be text up to 10,000 characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        business.notes = data["notes"]
    if "publicListing" in data and not isinstance(data["publicListing"], bool):
        return error(
            "invalid_listing", "Public listing must be true or false.", status.HTTP_400_BAD_REQUEST
        )
    correction = None
    if "correctedLatitude" in data or "correctedLongitude" in data:
        if "correctedLatitude" not in data or "correctedLongitude" not in data:
            return error(
                "invalid_correction",
                "Send both corrected coordinates.",
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            lat = Decimal(str(data["correctedLatitude"]))
            lng = Decimal(str(data["correctedLongitude"]))
        except InvalidOperation, TypeError, ValueError:
            return error(
                "invalid_correction",
                "Coordinates must be decimal numbers.",
                status.HTTP_400_BAD_REQUEST,
            )
        if (
            not lat.is_finite()
            or not lng.is_finite()
            or not -90 <= lat <= 90
            or not -180 <= lng <= 180
        ):
            return error(
                "invalid_correction", "Coordinates are out of range.", status.HTTP_400_BAD_REQUEST
            )
        if (
            lat < Decimal(str(settings.SERVICE_REGION_MIN_LAT))
            or lat > Decimal(str(settings.SERVICE_REGION_MAX_LAT))
            or lng < Decimal(str(settings.SERVICE_REGION_MIN_LNG))
            or lng > Decimal(str(settings.SERVICE_REGION_MAX_LNG))
        ):
            return error(
                "invalid_correction",
                "Corrected pin is outside the configured service area.",
                status.HTTP_400_BAD_REQUEST,
            )
        correction = (
            lat.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
            lng.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        )
    if "assignee" in data:
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        try:
            assignee = (
                user_model.objects.filter(
                    pk=data["assignee"],
                    is_active=True,
                    groups__name__in=["dispatcher", "admin", "field_team"],
                )
                .distinct()
                .first()
            )
            if assignee is None:
                raise user_model.DoesNotExist
        except user_model.DoesNotExist, TypeError, ValueError:
            return error(
                "invalid_assignee", "Choose an active staff account.", status.HTTP_400_BAD_REQUEST
            )
        business.assigned_to = assignee
    with transaction.atomic():
        if business.phone != original_phone:
            locked_business = (
                CustomerBusiness.objects.select_for_update(of=("self",))
                .select_related("location")
                .get(pk=business.pk)
            )
            if locked_business.phone != original_phone:
                return error(
                    "phone_changed_concurrently",
                    "Refresh the customer record and try again.",
                    status.HTTP_409_CONFLICT,
                )
            acquire_submission_locks(
                phone=original_phone,
                other_phones=(business.phone,),
                latitude=locked_business.location.latitude,
                longitude=locked_business.location.longitude,
            )
            old_phone_hash = hash_value("provider-phone:" + original_phone)
            new_phone_hash = hash_value("provider-phone:" + business.phone)
            codes = list(
                ProviderCode.objects.select_for_update()
                .filter(business=locked_business, target_phone_hash=old_phone_hash)
                .exclude(status=ProviderCode.Status.REVOKED)
            )
            for code in codes:
                code.target_phone_hash = new_phone_hash
                code.target_phone_last4 = business.phone[-4:]
            if codes:
                ProviderCode.objects.bulk_update(codes, ["target_phone_hash", "target_phone_last4"])
            legacy_codes = list(
                ProviderCode.objects.select_for_update()
                .filter(
                    business__isnull=True,
                    legacy_phone_lookup=True,
                    target_phone_hash=old_phone_hash,
                )
                .exclude(status=ProviderCode.Status.REVOKED)
            )
            legacy_ids = [code.pk for code in legacy_codes]
            legacy_keys_bound = 0
            legacy_shared_phone = CustomerBusiness.objects.filter(phone=original_phone).exclude(
                pk=locked_business.pk
            ).exists()
            if legacy_codes and not legacy_shared_phone:
                for code in legacy_codes:
                    code.business = locked_business
                    code.legacy_phone_lookup = False
                    code.target_phone_hash = new_phone_hash
                    code.target_phone_last4 = business.phone[-4:]
                ProviderCode.objects.bulk_update(
                    legacy_codes,
                    ["business", "legacy_phone_lookup", "target_phone_hash", "target_phone_last4"],
                )
                VerificationSession.objects.filter(
                    provider_code_id__in=legacy_ids, used_at__isnull=True
                ).update(used_at=timezone.now())
                legacy_keys_bound = len(legacy_ids)
                legacy_ids = []
            elif legacy_ids:
                revoked_at = timezone.now()
                VerificationSession.objects.filter(
                    provider_code_id__in=legacy_ids, used_at__isnull=True
                ).update(used_at=revoked_at)
                ProviderCode.objects.filter(pk__in=legacy_ids).update(
                    status=ProviderCode.Status.REVOKED,
                    revoked_at=revoked_at,
                    target_phone_hash="",
                    target_phone_last4="",
                )
            locked_business.phone = business.phone
            locked_business.save(update_fields=["phone", "updated_at"])
            record_audit(
                request=request,
                actor=request.user,
                action="business.phone_changed",
                object_type="CustomerBusiness",
                object_id=business.pk,
                metadata={
                    "changed_fields": ["phone"],
                    "ambiguous_legacy_keys_revoked": len(legacy_ids),
                    "legacy_keys_bound": legacy_keys_bound,
                },
            )
        if "publicListing" in data:
            business.consent.public_listing = data["publicListing"]
            business.consent.save(update_fields=["public_listing"])
        if correction:
            business.location.corrected_lat, business.location.corrected_lng = correction
            business.location.corrected_by = request.user
            business.location.corrected_at = timezone.now()
            business.location.team_verified = True
            business.location.save(
                update_fields=[
                    "corrected_lat",
                    "corrected_lng",
                    "corrected_by",
                    "corrected_at",
                    "team_verified",
                ]
            )
            record_audit(
                request=request,
                actor=request.user,
                action="location.corrected",
                object_type="CustomerBusiness",
                object_id=business.pk,
            )
        business.save()
        field_names = {
            "customerName": "customer_name",
            "businessName": "business_name",
            "phone": "phone",
            "status": "status",
            "notes": "notes",
            "assignee": "assigned_to",
            "publicListing": "public_listing",
            "correctedLatitude": "location",
            "correctedLongitude": "location",
        }
        record_audit(
            request=request,
            actor=request.user,
            action="business.updated",
            object_type="CustomerBusiness",
            object_id=business.pk,
            metadata={"changed_fields": sorted({field_names[name] for name in data})},
        )
    business.refresh_from_db()
    return Response(serialize_staff_business(business, detail=True))


@api_view(["GET", "POST"])
@permission_classes([AuditIsAuthenticated])
def admin_business_flag_cases(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
    if not (has_role(request.user, "dispatcher") or has_role(request.user, "admin")):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "customer_flag_role_required"},
        )
        return error("customer_flag_role_required", "Only dispatchers and administrators can flag customers.", 403)
    business = CustomerBusiness.objects.filter(pk=business_id).first()
    if business is None:
        return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
    cases = CustomerFlagCase.objects.filter(business=business).select_related("created_by")
    if request.method == "GET":
        record_audit(
            request=request,
            actor=request.user,
            action="customer.flag_cases_viewed",
            object_type="CustomerBusiness",
            object_id=business.pk,
        )
        return Response(
            {
                "items": [
                    {
                        "id": case.pk,
                        "reference": case.business_reference,
                        "category": case.category,
                        "categoryLabel": case.get_category_display(),
                        "details": case.details,
                        "status": case.status,
                        "createdBy": case.created_by.get_username() if case.created_by else "Staff",
                        "createdAt": case.created_at,
                    }
                    for case in cases
                ]
            }
        )
    data = request.data
    category = data.get("category") if isinstance(data, dict) else None
    details = data.get("details") if isinstance(data, dict) else None
    if category not in CustomerFlagCase.Category.values:
        return error("invalid_flag_category", "Choose a valid flag category.", 400)
    if not isinstance(details, str) or not 10 <= len(details.strip()) <= 1200:
        return error("invalid_flag_details", "Add a short note of 10–1,200 characters.", 400)
    with transaction.atomic():
        business = CustomerBusiness.objects.select_for_update().filter(pk=business_id).first()
        if business is None:
            return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
        case = CustomerFlagCase.objects.create(
            business=business,
            business_reference=business.public_ref,
            category=category,
            details=details.strip(),
            created_by=request.user,
        )
        record_audit(
            request=request,
            actor=request.user,
            action="customer.flag_case_opened",
            object_type="CustomerFlagCase",
            object_id=case.pk,
            metadata={"category": case.category, "reference": case.business_reference},
        )
    return Response(
        {
            "id": case.pk,
            "category": case.category,
            "categoryLabel": case.get_category_display(),
            "status": case.status,
            "createdAt": case.created_at,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_business_visits(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
    if has_role(request.user, "field_team") and not request.user.is_superuser:
        return error("field_team_visit_forbidden", "Field team members cannot edit visit records.", 403)
    business = CustomerBusiness.objects.filter(pk=business_id).first()
    if business is None:
        return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
    visit_date = parse_date(str(request.data.get("visitDate", "")))
    team = request.data.get("team", "")
    outcome = request.data.get("outcome", "")
    if (
        visit_date is None
        or not isinstance(team, str)
        or len(team) > 160
        or not isinstance(outcome, str)
        or len(outcome) > 500
    ):
        return error(
            "invalid_visit",
            "Provide a valid visit date, team, and outcome.",
            status.HTTP_400_BAD_REQUEST,
        )
    visit = ServiceVisit.objects.create(
        business=business,
        visit_date=visit_date,
        team=team,
        outcome=outcome,
        created_by=request.user,
    )
    record_audit(
        request=request,
        actor=request.user,
        action="visit.created",
        object_type="CustomerBusiness",
        object_id=business.pk,
    )
    return Response(
        {"id": visit.pk, "visitDate": visit.visit_date.isoformat()}, status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_business_arrival_check(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
    if not has_role(request.user, "field_team") or request.user.is_superuser:
        return error("field_team_required", "This check is for field team members.", 403)
    business = CustomerBusiness.objects.select_related("location").filter(pk=business_id).first()
    if business is None or business.assigned_to_id != request.user.pk:
        return error("not_found", "Assigned business not found.", 404)
    try:
        latitude = Decimal(str(request.data.get("latitude")))
        longitude = Decimal(str(request.data.get("longitude")))
        accuracy = Decimal(str(request.data.get("accuracyMeters")))
        captured = parse_datetime(str(request.data.get("fixTimestamp", "")))
        if not latitude.is_finite() or not longitude.is_finite() or not accuracy.is_finite():
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        return error("invalid_location", "Capture your position again and retry.", 422)
    now = timezone.now()
    if (
        latitude < Decimal(str(settings.SERVICE_REGION_MIN_LAT))
        or latitude > Decimal(str(settings.SERVICE_REGION_MAX_LAT))
        or longitude < Decimal(str(settings.SERVICE_REGION_MIN_LNG))
        or longitude > Decimal(str(settings.SERVICE_REGION_MAX_LNG))
        or accuracy < 0
        or accuracy > Decimal(str(settings.LOCATION_MAX_ACCURACY_M))
        or captured is None
        or timezone.is_naive(captured)
    ):
        return error(
            "invalid_location", "The location reading is not usable. Retry the check.", 422
        )
    age = (now - captured).total_seconds()
    if (
        age < -settings.LOCATION_FUTURE_SKEW_SECONDS
        or age > settings.LOCATION_MAX_FIX_AGE_SECONDS
    ):
        return error(
            "stale_location",
            "The location reading is too old or has an invalid time. Retry.",
            422,
        )
    destination_lat = float(business.location.navigation_latitude)
    destination_lng = float(business.location.navigation_longitude)
    earth_radius_m = 6371008.8
    lat1, lat2 = math.radians(float(latitude)), math.radians(destination_lat)
    delta_lat = lat2 - lat1
    delta_lng = math.radians(destination_lng - float(longitude))
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    distance_m = earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    if distance_m < 50:
        distance_band = "under_50m"
    elif distance_m < 250:
        distance_band = "50_to_250m"
    else:
        distance_band = "over_250m"
    record_audit(
        request=request,
        actor=request.user,
        action="location.arrival_checked",
        object_type="CustomerBusiness",
        object_id=business.pk,
        metadata={"distance_band": distance_band},
    )
    return Response({"distanceMeters": round(distance_m), "accuracyMeters": float(accuracy)})


def csv_safe_text(value):
    value = "" if value is None else str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@api_view(["GET"])
@permission_classes([AuditIsAuthenticated])
def admin_export(request):
    denied = staff_required(request, admin=True)
    if denied:
        return denied
    record_audit(
        request=request,
        actor=request.user,
        action="business.exported",
        object_type="CustomerBusiness",
        object_id="all",
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "reference",
            "customer_name",
            "business_name",
            "phone",
            "status",
            "latitude",
            "longitude",
            "accuracy_m",
            "ward",
            "district",
            "region",
        ]
    )
    rows = CustomerBusiness.objects.select_related("location").order_by("created_at")
    for business in rows.iterator():
        loc = business.location
        writer.writerow(
            [
                business.public_ref,
                csv_safe_text(business.customer_name),
                csv_safe_text(business.business_name),
                csv_safe_text(business.phone),
                business.status,
                str(loc.navigation_latitude),
                str(loc.navigation_longitude),
                str(loc.accuracy_m or ""),
                csv_safe_text(loc.ward),
                csv_safe_text(loc.district),
                csv_safe_text(loc.region),
            ]
        )
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="businesses.csv"'
    response["Cache-Control"] = "no-store"
    return response


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_provider_codes(request):
    if (
        not admin_or_superuser(request.user)
        and not request.user.groups.filter(name="service_provider").exists()
    ):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "provider_role_required"},
        )
        return error(
            "provider_role_required",
            "Provider-code access is limited to administrators and service providers.",
            status.HTTP_403_FORBIDDEN,
        )
    is_provider = (
        not request.user.is_superuser
        and request.user.groups.filter(name="service_provider").exists()
    )
    is_search = request.data.get("action") == "search"
    if not is_search and not service_provider_or_superuser(request.user):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "code_issue_role_required"},
        )
        return error(
            "code_issue_role_required",
            "Only the superuser and service providers can generate customer keys.",
            status.HTTP_403_FORBIDDEN,
        )
    if is_search:
        codes = ProviderCode.objects.all()
        if is_provider:
            codes = codes.filter(created_by=request.user)
        query = str(request.data.get("q", "")).strip()[:120]
        status_filter = str(request.data.get("status", "")).strip()
        now = timezone.now()
        if status_filter == "active":
            codes = codes.filter(status=ProviderCode.Status.ACTIVE, expires_at__gt=now).filter(
                Q(reusable=True) | Q(use_count__lt=F("max_uses"))
            )
        elif status_filter == "expired":
            codes = codes.filter(
                Q(status=ProviderCode.Status.EXPIRED)
                | Q(status=ProviderCode.Status.ACTIVE, expires_at__lte=now)
            )
        elif status_filter == "used":
            codes = codes.filter(
                status=ProviderCode.Status.ACTIVE,
                reusable=False,
                expires_at__gt=now,
                use_count__gte=F("max_uses"),
            )
        elif status_filter == "revoked":
            codes = codes.filter(status=ProviderCode.Status.REVOKED)
        elif status_filter:
            return error(
                "invalid_status", "Unknown provider code status.", status.HTTP_400_BAD_REQUEST
            )

        if query and is_provider:
            digits_query = "".join(char for char in query if char.isdigit())
            search_filter = Q(label__icontains=query)
            if len(digits_query) >= 4:
                search_filter |= Q(target_phone_last4=digits_query[-4:])
            codes = codes.filter(search_filter)
        elif query:
            matching_businesses = CustomerBusiness.objects.filter(
                Q(customer_name__icontains=query)
                | Q(business_name__icontains=query)
                | Q(phone__icontains=query)
            ).values_list("phone", flat=True)
            phone_hashes = [hash_value("provider-phone:" + phone) for phone in matching_businesses]
            search_filter = Q(label__icontains=query) | Q(target_phone_hash__in=phone_hashes)
            if query.isdigit() and len(query) <= 9:
                search_filter |= Q(pk=int(query))
            try:
                normalized_query = normalize_phone(query)
                search_filter |= Q(
                    target_phone_hash=hash_value("provider-phone:" + normalized_query)
                )
            except ValidationError:
                pass
            digits_query = "".join(char for char in query if char.isdigit())
            if len(digits_query) >= 4:
                search_filter |= Q(target_phone_last4=digits_query[-4:])
            codes = codes.filter(search_filter)

        try:
            page = max(1, int(request.data.get("page", "1")))
        except ValueError:
            return error(
                "invalid_page", "Page must be a whole number.", status.HTTP_400_BAD_REQUEST
            )
        awaiting_codes = ProviderCode.objects.filter(
            business__isnull=True,
            status=ProviderCode.Status.ACTIVE,
            expires_at__gt=now,
        ).filter(Q(reusable=True) | Q(use_count__lt=F("max_uses")))
        if is_provider:
            awaiting_codes = awaiting_codes.filter(created_by=request.user)
        awaiting_submission = awaiting_codes.count()
        page_size = 50
        count = codes.count()
        pages = max(1, math.ceil(count / page_size))
        page = min(page, pages)
        page_codes = list(
            codes.select_related("business").order_by("-created_at")[
                (page - 1) * page_size : page * page_size
            ]
        )
        target_hashes = {code.target_phone_hash for code in page_codes}
        linked_customers = {}
        if target_hashes:
            # Match provider-key digests against indexed customer phone digests.
            linked_rows = (
                CustomerBusiness.objects.filter(phone_hash__in=target_hashes)
                .only("phone_hash", "customer_name", "business_name", "phone")
                .order_by("-created_at")
            )
            grouped = {}
            for business in linked_rows:
                phone_hash = hash_value("provider-phone:" + business.phone)
                if phone_hash in target_hashes:
                    grouped.setdefault(phone_hash, []).append(business)
            linked_customers = {
                phone_hash: rows[0] for phone_hash, rows in grouped.items() if len(rows) == 1
            }
        items = []
        for code in page_codes:
            if code.status == ProviderCode.Status.REVOKED:
                code_status = "revoked"
            elif code.status == ProviderCode.Status.EXPIRED or code.expires_at <= now:
                code_status = "expired"
            elif not code.reusable and code.use_count >= code.max_uses:
                code_status = "used"
            else:
                code_status = "active"
            customer = (
                code.business
                or (linked_customers.get(code.target_phone_hash) if code.legacy_phone_lookup else None)
            ) if not is_provider else None
            items.append(
                {
                    "id": code.pk,
                    "label": code.label,
                    "status": code_status,
                    "expiresAt": code.expires_at.isoformat(),
                    "createdAt": code.created_at.isoformat(),
                    "maxUses": code.max_uses,
                    "useCount": code.use_count,
                    "reusable": code.reusable,
                    "businessId": str(code.business_id)
                    if code.business_id
                    and (not is_provider or code.created_by_id == request.user.pk)
                    else None,
                    "needsResolution": bool(
                        not is_provider and code.business_id is None and code.legacy_phone_lookup
                    ),
                    "customerName": customer.customer_name if customer else None,
                    "businessName": customer.business_name if customer else None,
                    "phone": customer.phone
                    if customer
                    else (
                        "•••• " + code.target_phone_last4
                        if code.target_phone_last4
                        else None
                    ),
                }
            )
        record_audit(
            request=request,
            actor=request.user,
            action="provider_code.list_viewed",
            object_type="ProviderCode",
            object_id="",
        )
        return Response(
            {"count": count, "page": page, "pages": pages, "awaitingSubmission": awaiting_submission, "items": items}
        )
    expires_at = parse_datetime(str(request.data.get("expiresAt", "")))
    raw_phone = request.data.get("phone", "")
    try:
        phone = normalize_phone(raw_phone) if isinstance(raw_phone, str) else ""
    except ValidationError:
        phone = ""
    label = request.data.get("label", "")
    business_id = request.data.get("businessId")
    business = None
    if business_id:
        try:
            business_id = uuid.UUID(str(business_id))
        except (ValueError, TypeError, AttributeError):
            return error("invalid_business", "Choose a valid existing business.", 400)
        may_link_business = request.user.is_superuser or has_role(request.user, "admin")
        if is_provider:
            may_link_business = ProviderCode.objects.filter(
                business_id=business_id, created_by=request.user
            ).exists()
        if not may_link_business:
            return error("provider_business_link_forbidden", "You cannot link a key to this business profile.", 403)
        business = CustomerBusiness.objects.filter(pk=business_id).first()
        if business is None or business.phone != phone:
            return error("invalid_business", "Choose an existing business with this phone number.", 400)
    if (
        not phone
        or expires_at is None
        or timezone.is_naive(expires_at)
        or expires_at <= timezone.now()
        or not isinstance(label, str)
        or len(label) > 120
    ):
        return error(
            "invalid_provider_code",
            "Provide a valid customer phone, a future timezone-aware expiry, and a label up to "
            "120 characters.",
            status.HTTP_400_BAD_REQUEST,
        )
    code, raw_code = issue_provider_code(
        target_phone=phone,
        expires_at=expires_at,
        max_uses=1,
        label=label,
        created_by=request.user,
        reusable=True,
        business=business,
    )
    record_audit(
        request=request,
        actor=request.user,
        action="provider_code.created",
        object_type="ProviderCode",
        object_id=code.pk,
    )
    return Response(
        {
            "id": code.pk,
            "code": raw_code,
            "phone": phone,
            "expiresAt": code.expires_at.isoformat(),
            "reusable": True,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_link_legacy_code(request, code_id):
    denied = staff_required(request, admin=True)
    if denied:
        return denied
    try:
        business_id = uuid.UUID(str(request.data.get("businessId", "")))
    except (ValueError, TypeError, AttributeError):
        return error("invalid_business", "Choose a valid business profile.", 400)

    with transaction.atomic():
        code = ProviderCode.objects.select_for_update().filter(pk=code_id).first()
        if code is None:
            return error("not_found", "Customer key not found.", 404)
        if code.business_id is not None or not code.legacy_phone_lookup:
            return error(
                "legacy_key_already_resolved",
                "This key is already linked or is not an unresolved legacy key.",
                409,
            )
        if not code.accepts():
            return error("legacy_key_inactive", "Only an active key can be linked.", 409)
        business = CustomerBusiness.objects.filter(pk=business_id).first()
        if business is None or not hmac.compare_digest(
            code.target_phone_hash, hash_value("provider-phone:" + business.phone)
        ):
            return error(
                "legacy_key_phone_mismatch",
                "The selected business does not match this key’s phone number.",
                400,
            )
        code.business = business
        code.legacy_phone_lookup = False
        code.save(update_fields=["business", "legacy_phone_lookup"])
        record_audit(
            request=request,
            actor=request.user,
            action="provider_code.legacy_linked",
            object_type="ProviderCode",
            object_id=code.pk,
            metadata={"business_id": str(business.pk)},
        )
    return Response({"linked": True, "businessId": str(business.pk), "reference": business.public_ref})


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_revoke_code(request, code_id):
    is_owner_provider = (
        request.user.groups.filter(name="service_provider").exists()
        and not request.user.is_superuser
    )
    if not admin_or_superuser(request.user) and not is_owner_provider:
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "code_revoke_role_required"},
        )
        return error(
            "provider_revoke_role_required",
            "Only an administrator or service provider can revoke a customer key.",
            status.HTTP_403_FORBIDDEN,
        )
    code = ProviderCode.objects.filter(pk=code_id).first()
    if code is None:
        return error("not_found", "Provider code not found.", status.HTTP_404_NOT_FOUND)
    if is_owner_provider and code.created_by_id != request.user.pk:
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="ProviderCode",
            object_id=code.pk,
            metadata={"reason": "provider_not_owner"},
        )
        return error(
            "provider_key_owner_required",
            "Service providers can revoke only keys they created.",
            status.HTTP_403_FORBIDDEN,
        )
    if code.status != ProviderCode.Status.REVOKED:
        code.status = ProviderCode.Status.REVOKED
        code.revoked_at = timezone.now()
        code.save(update_fields=["status", "revoked_at"])
    record_audit(
        request=request,
        actor=request.user,
        action="provider_code.revoked",
        object_type="ProviderCode",
        object_id=code.pk,
    )
    return Response({"revoked": True})


@api_view(["GET"])
@permission_classes([AuditIsAuthenticated])
def admin_audit_log(request):
    denied = staff_required(request, admin=True)
    if denied:
        return denied
    events = AuditLog.objects.select_related("actor").order_by("-timestamp")[:200]
    record_audit(
        request=request,
        actor=request.user,
        action="audit_log.viewed",
        object_type="AuditLog",
        object_id="recent",
    )
    return Response(
        {
            "items": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor.get_username() if event.actor else None,
                    "action": event.action,
                    "objectType": event.object_type,
                    "objectId": event.object_id,
                }
                for event in events
            ]
        }
    )
