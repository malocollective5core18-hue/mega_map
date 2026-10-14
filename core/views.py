import csv
import base64
import hashlib
import hmac
import io
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.db.models import F, Q
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


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_shops(request):
    try:
        bbox = parse_bbox(request.query_params.get("bbox"))
    except ValueError as exc:
        return error("invalid_bbox", str(exc), status.HTTP_400_BAD_REQUEST)
    try:
        limit = min(500, max(1, int(request.query_params.get("limit", "500"))))
    except ValueError:
        return error(
            "invalid_limit",
            "Limit must be a whole number from 1 to 500.",
            status.HTTP_400_BAD_REQUEST,
        )
    rows = public_businesses_in_bbox(bbox).order_by("public_ref")[:limit]
    return Response({"items": [serialize_public_shop(row) for row in rows]})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_shop_search(request):
    query = request.query_params.get("q", "").strip()
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


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_demand_cells(request):
    try:
        bbox = parse_bbox(request.query_params.get("bbox"))
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
            "whatsappNumber": getattr(settings, "COMPANY_WHATSAPP_NUMBER", ""),
            "phoneNumber": getattr(settings, "COMPANY_PHONE_NUMBER", ""),
            "privacyNoticeVersion": settings.PRIVACY_NOTICE_VERSION,
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
            .filter(phone=phone)
            .order_by("-created_at")
            .first()
        )
        if customer is not None:
            result["existingCustomer"] = {
                "reference": customer.public_ref,
                "customerName": customer.customer_name,
                "businessName": customer.business_name,
                "phone": customer.phone,
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
            expected_phone_hash = session.provider_code.target_phone_hash
            if not expected_phone_hash or not hmac.compare_digest(
                expected_phone_hash, hash_value("provider-phone:" + data["phone"])
            ):
                return error(
                    "phone_code_mismatch",
                    "Use the phone number associated with this service code.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            acquire_submission_locks(
                phone=data["phone"], latitude=data["latitude"], longitude=data["longitude"]
            )
            if find_duplicate(
                phone=data["phone"], latitude=data["latitude"], longitude=data["longitude"]
            ):
                body = {
                    "error": {
                        "code": "duplicate",
                        "message": "A request for this phone or location already exists.",
                    }
                }
                session.used_at = timezone.now()
                session.save(update_fields=["used_at"])
                IdempotencyRecord.objects.create(
                    key_hash=key_hash, session=session, response_status=409, response_body=body
                )
                return Response(body, status=status.HTTP_409_CONFLICT)
            business = record_submission(data=data, request=request)
            body = {"accepted": True, "reference": business.public_ref}
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
                .filter(phone=data["phone"])
                .order_by("-created_at")
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
            business.location.source = (
                BusinessLocation.Source.GPS
                if data.get("accuracyMeters") is not None
                else BusinessLocation.Source.MANUAL
            )
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
            body = {"updated": True, "reference": business.public_ref}
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
            "not_allowed", "This action is limited to administrators.", status.HTTP_403_FORBIDDEN
        )
    if not role and not (has_role(request.user, "dispatcher") or has_role(request.user, "admin")):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "staff_role_required"},
        )
        return error("not_allowed", "This action is limited to staff.", status.HTTP_403_FORBIDDEN)
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
            "not_allowed",
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
    else:
        role = "dispatcher"

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
        return error("not_allowed", "Staff MFA enrollment is unavailable.", 403)
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
        return error("not_allowed", "Staff MFA enrollment is unavailable.", 403)
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
        return error("not_allowed", "Verified staff sign-in is required.", 403)
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
        return error("not_allowed", "The configured MFA recovery owner must approve this action.", 403)
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
            User.objects.filter(groups__name__in=["admin", "service_provider"])
            .distinct()
            .order_by("username")
        )
        items = [
            {
                "id": user.pk,
                "username": user.get_username(),
                "email": user.email,
                "role": "service_provider"
                if user.groups.filter(name="service_provider").exists()
                else "admin",
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
        or role not in ("admin", "service_provider")
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
        "openStreetMap": f"https://www.openstreetmap.org/?mlat={lat_text}&mlon={lng_text}#map=19/{lat_text}/{lng_text}",
        "whatsappShare": f"https://wa.me/?text={quote(google_driving, safe='')}",
    }


def location_confidence(location):
    if location.source == BusinessLocation.Source.MANUAL or location.accuracy_m is None:
        return {"level": "low", "message": "Call the customer to confirm before travelling."}
    accuracy = float(location.accuracy_m)
    if accuracy <= 30:
        return {"level": "high", "message": ""}
    if accuracy <= 100:
        return {
            "level": "medium",
            "message": "Check the pin and allow extra time to confirm the entrance.",
        }
    return {"level": "low", "message": "Call the customer to confirm before travelling."}


def phone_access(phone):
    codes = ProviderCode.objects.filter(target_phone_hash=hash_value("provider-phone:" + phone))
    code = (
        codes.filter(status=ProviderCode.Status.ACTIVE, expires_at__gt=timezone.now())
        .filter(Q(reusable=True) | Q(use_count__lt=F("max_uses")))
        .order_by("-created_at")
        .first()
    )
    if code is not None:
        return {"status": "active", "expiresAt": code.expires_at.isoformat()}
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


def serialize_staff_business(business, *, detail=False):
    location = business.location
    result = {
        "id": str(business.pk),
        "reference": business.public_ref,
        "businessName": business.business_name,
        "customerName": business.customer_name,
        "phone": business.phone,
        "accountAccess": phone_access(business.phone),
        "status": business.status,
        "accuracyMeters": float(location.accuracy_m) if location.accuracy_m is not None else None,
        "latitude": float(location.navigation_latitude),
        "longitude": float(location.navigation_longitude),
        "locationConfidence": location_confidence(location),
        "navigationLinks": navigation_links(location),
        "teamVerified": location.team_verified,
        "publicListing": business.consent.public_listing,
        "createdAt": business.created_at.isoformat(),
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


@api_view(["GET"])
@permission_classes([AuditIsAuthenticated])
def admin_businesses(request):
    denied = staff_required(request)
    if denied:
        return denied
    businesses = CustomerBusiness.objects.select_related("location", "consent", "assigned_to")
    status_filter = request.query_params.get("status", "").strip()
    if status_filter:
        if status_filter not in CustomerBusiness.Status.values:
            return error("invalid_status", "Unknown business status.", status.HTTP_400_BAD_REQUEST)
        businesses = businesses.filter(status=status_filter)
    query = request.query_params.get("q", "").strip()
    if query:
        businesses = businesses.filter(
            Q(public_ref__icontains=query)
            | Q(business_name__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(phone__icontains=query)
        )
    bbox_arg = request.query_params.get("bbox")
    if bbox_arg:
        try:
            businesses = current_location_filter(businesses, parse_bbox(bbox_arg))
        except ValueError as exc:
            return error("invalid_bbox", str(exc), status.HTTP_400_BAD_REQUEST)
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        return error("invalid_page", "Page must be a whole number.", status.HTTP_400_BAD_REQUEST)
    page_size = 50
    count = businesses.count()
    record_audit(
        request=request,
        actor=request.user,
        action="business.list_viewed",
        object_type="CustomerBusiness",
        object_id="",
    )
    rows = businesses.order_by("-created_at")[(page - 1) * page_size : page * page_size]
    return Response(
        {"count": count, "page": page, "items": [serialize_staff_business(row) for row in rows]}
    )


@api_view(["GET", "PATCH"])
@permission_classes([AuditIsAuthenticated])
def admin_business_detail(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
    business = (
        CustomerBusiness.objects.select_related("location", "consent", "assigned_to")
        .filter(pk=business_id)
        .first()
    )
    if business is None:
        return error("not_found", "Business not found.", status.HTTP_404_NOT_FOUND)
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
            "not_allowed",
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
                    pk=data["assignee"], is_active=True, groups__name__in=["dispatcher", "admin"]
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
                CustomerBusiness.objects.select_for_update()
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
            if (
                CustomerBusiness.objects.filter(phone=business.phone)
                .exclude(pk=business.pk)
                .exists()
            ):
                return error(
                    "phone_in_use",
                    "That phone number is already assigned to another business.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            old_phone_hash = hash_value("provider-phone:" + original_phone)
            new_phone_hash = hash_value("provider-phone:" + business.phone)
            codes = list(
                ProviderCode.objects.select_for_update()
                .filter(target_phone_hash=old_phone_hash)
                .exclude(status=ProviderCode.Status.REVOKED)
            )
            for code in codes:
                code.target_phone_hash = new_phone_hash
                code.target_phone_last4 = business.phone[-4:]
            if codes:
                ProviderCode.objects.bulk_update(codes, ["target_phone_hash", "target_phone_last4"])
            locked_business.phone = business.phone
            locked_business.save(update_fields=["phone", "updated_at"])
            record_audit(
                request=request,
                actor=request.user,
                action="business.phone_changed",
                object_type="CustomerBusiness",
                object_id=business.pk,
                metadata={"changed_fields": ["phone"]},
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


@api_view(["POST"])
@permission_classes([AuditIsAuthenticated])
def admin_business_visits(request, business_id):
    denied = staff_required(request)
    if denied:
        return denied
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


@api_view(["GET", "POST"])
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
            "not_allowed",
            "Provider-code access is limited to administrators and service providers.",
            status.HTTP_403_FORBIDDEN,
        )
    is_provider = (
        not request.user.is_superuser
        and request.user.groups.filter(name="service_provider").exists()
    )
    if request.method == "POST" and not service_provider_or_superuser(request.user):
        record_audit(
            request=request,
            actor=request.user,
            action="auth.authorization_denied",
            object_type="StaffEndpoint",
            object_id=request.path,
            metadata={"reason": "code_issue_role_required"},
        )
        return error(
            "not_allowed",
            "Only the superuser and service providers can generate customer keys.",
            status.HTTP_403_FORBIDDEN,
        )
    if request.method == "GET":
        codes = ProviderCode.objects.all()
        if is_provider:
            codes = codes.filter(created_by=request.user)
        query = request.query_params.get("q", "").strip()[:120]
        status_filter = request.query_params.get("status", "").strip()
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
            page = max(1, int(request.query_params.get("page", "1")))
        except ValueError:
            return error(
                "invalid_page", "Page must be a whole number.", status.HTTP_400_BAD_REQUEST
            )
        page_size = 50
        count = codes.count()
        page_codes = list(codes.order_by("-created_at")[(page - 1) * page_size : page * page_size])
        target_hashes = {code.target_phone_hash for code in page_codes}
        linked_customers = {}
        if target_hashes:
            # Match provider-key digests against indexed customer phone digests.
            linked_rows = (
                CustomerBusiness.objects.filter(phone_hash__in=target_hashes)
                .only("phone_hash", "customer_name", "business_name", "phone")
                .order_by("-created_at")
            )
            for business in linked_rows:
                phone_hash = hash_value("provider-phone:" + business.phone)
                if phone_hash in target_hashes and phone_hash not in linked_customers:
                    linked_customers[phone_hash] = business
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
            customer = linked_customers.get(code.target_phone_hash) if not is_provider else None
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
                    "customerName": customer.customer_name if customer else None,
                    "businessName": customer.business_name if customer else None,
                    "phone": customer.phone
                    if customer
                    else ("•••• " + code.target_phone_last4 if code.target_phone_last4 else None),
                }
            )
        record_audit(
            request=request,
            actor=request.user,
            action="provider_code.list_viewed",
            object_type="ProviderCode",
            object_id="",
        )
        return Response({"count": count, "page": page, "items": items})
    expires_at = parse_datetime(str(request.data.get("expiresAt", "")))
    raw_phone = request.data.get("phone", "")
    try:
        phone = normalize_phone(raw_phone) if isinstance(raw_phone, str) else ""
    except ValidationError:
        phone = ""
    label = request.data.get("label", "")
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
            "not_allowed",
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
            "not_allowed",
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
