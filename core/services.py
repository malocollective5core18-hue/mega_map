import hashlib
import math
import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import connection

from .models import BusinessLocation, Consent, CustomerBusiness
from .security import hash_ip, hash_value, record_audit


def acquire_submission_locks(*, phone, latitude, longitude, other_phones=()):
    """Serialize duplicate checks for a phone and nearby map cells on PostgreSQL."""
    if connection.vendor != "postgresql":
        return
    if not connection.in_atomic_block:
        raise RuntimeError("Submission advisory locks require an active transaction.")

    def lock_id(value):
        return int.from_bytes(hashlib.sha256(value).digest()[:8], "big", signed=True)

    phone_values = {phone, *other_phones}
    locks = {
        lock_id(b"customer-phone:" + hash_value("provider-phone:" + value).encode("ascii"))
        for value in phone_values
    }
    lat = float(latitude)
    lng = float(longitude)
    lat_step = 30 / 111_320
    cosine = max(0.01, abs(math.cos(math.radians(lat))))
    lng_step = min(360.0, 30 / (111_320 * cosine))
    lat_cell = math.floor(lat / lat_step)
    lng_cell = math.floor(lng / lng_step)
    for lat_offset in (-1, 0, 1):
        for lng_offset in (-1, 0, 1):
            cell = f"{lat_cell + lat_offset}:{lng_cell + lng_offset}".encode("ascii")
            locks.add(lock_id(b"customer-location:" + cell))

    with connection.cursor() as cursor:
        for advisory_id in sorted(locks):
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [advisory_id])


def make_public_reference():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "BU-" + "".join(secrets.choice(alphabet) for _ in range(10))


def rounded_public_coordinate(value):
    return float(Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def find_duplicate(*, phone, latitude, longitude):
    if CustomerBusiness.objects.filter(phone=phone).exists():
        return True
    lat = float(latitude)
    lng = float(longitude)
    lat_delta = 30 / 111_320
    cos_lat = max(0.01, abs(math.cos(math.radians(lat))))
    lng_delta = min(180.0, 30 / (111_320 * cos_lat))
    candidates = BusinessLocation.objects.filter(
        latitude__gte=Decimal(str(lat - lat_delta)),
        latitude__lte=Decimal(str(lat + lat_delta)),
        longitude__gte=Decimal(str(lng - lng_delta)),
        longitude__lte=Decimal(str(lng + lng_delta)),
    ).select_related("business")
    for location in candidates.iterator():
        lat1, lon1 = math.radians(lat), math.radians(lng)
        lat2, lon2 = math.radians(float(location.latitude)), math.radians(float(location.longitude))
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))
        if distance <= 30:
            return True
    return False


def record_submission(*, data, request):
    business = CustomerBusiness.objects.create(
        public_ref=make_public_reference(),
        customer_name=data["customerName"],
        business_name=data["businessName"],
        phone=data["phone"],
    )
    BusinessLocation.objects.create(
        business=business,
        latitude=data["latitude"],
        longitude=data["longitude"],
        accuracy_m=data.get("accuracyMeters"),
        source=BusinessLocation.Source.GPS
        if data.get("accuracyMeters") is not None
        else BusinessLocation.Source.MANUAL,
    )
    Consent.objects.create(
        business=business,
        privacy_notice_version=settings.PRIVACY_NOTICE_VERSION,
        location_processing=True,
        public_listing=data["publicListing"],
        ip_hash=hash_ip(request),
    )
    record_audit(
        request=request,
        action="location.submitted",
        object_type="CustomerBusiness",
        object_id=business.pk,
    )
    return business


def geometry_bounds(geojson):
    if not isinstance(geojson, dict):
        return None
    if geojson.get("type") == "Feature":
        return geometry_bounds(geojson.get("geometry"))
    if geojson.get("type") == "GeometryCollection":
        bounds = [geometry_bounds(g) for g in geojson.get("geometries", [])]
        bounds = [b for b in bounds if b]
        if not bounds:
            return None
        return (
            min(b[0] for b in bounds),
            min(b[1] for b in bounds),
            max(b[2] for b in bounds),
            max(b[3] for b in bounds),
        )
    coords = geojson.get("coordinates")
    points = []

    def collect(value):
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and all(isinstance(n, (int, float)) for n in value[:2]):
                points.append((float(value[0]), float(value[1])))
            else:
                for item in value:
                    collect(item)

    collect(coords)
    if not points:
        return None
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)
