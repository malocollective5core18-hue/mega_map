import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from html.parser import HTMLParser
from struct import unpack
from threading import Barrier, BrokenBarrierError
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from .models import (
    AuditLog,
    BusinessLocation,
    CodeAttempt,
    Consent,
    CustomerBusiness,
    DemandCell,
    ProviderCode,
    VerificationSession,
    StaffMFARecoveryCode,
)
from .security import code_attempts_throttled, hash_value
from .services import find_duplicate as real_find_duplicate


class _PageHeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = {}
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key] = attrs.get("content", "")
        elif tag == "link":
            rel = attrs.get("rel", "")
            self.links[rel] = attrs.get("href", "")
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class LinkPreviewMetadataTests(TestCase):
    def setUp(self):
        self.site_url = "https://preview.example"
        self.client = APIClient()

    @override_settings(SITE_URL="https://preview.example")
    def test_public_home_has_complete_absolute_crawler_metadata(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        parser = _PageHeadParser()
        parser.feed(response.content.decode())
        raw_html = response.content.decode()

        self.assertEqual(parser.title, "Mauzosheet, Hotbano & Services")
        self.assertLessEqual(len(parser.title), 60)
        self.assertLessEqual(len(parser.meta["description"]), 155)
        self.assertEqual(parser.links["canonical"], f"{self.site_url}/")
        ordered_tags = (
            "<title>",
            'name="description"',
            'rel="canonical"',
            'property="og:type"',
            'name="twitter:card"',
            'name="theme-color"',
            'rel="icon"',
            'rel="apple-touch-icon"',
            'rel="manifest"',
            'name="robots"',
        )
        positions = [raw_html.index(tag) for tag in ordered_tags]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(max(positions), 8192)
        self.assertIn("apple-touch-icon", parser.links)
        self.assertIn("manifest", parser.links)
        expected = {
            "og:type": "website",
            "og:site_name": "Mauzosheet, Hotbano & Services",
            "og:title": parser.title,
            "og:description": parser.meta["description"],
            "og:url": f"{self.site_url}/",
            "og:image:type": "image/png",
            "og:image:width": "1200",
            "og:image:height": "630",
            "og:image:alt": "Mauzosheet map pin and business location service",
            "og:locale": "sw_TZ",
            "og:locale:alternate": "en_US",
            "twitter:card": "summary_large_image",
            "twitter:title": parser.title,
            "twitter:description": parser.meta["description"],
            "twitter:image:alt": "Mauzosheet map pin and business location service",
            "theme-color": "#0f3d2e",
            "robots": "index,follow",
        }
        for key, value in expected.items():
            with self.subTest(meta=key):
                self.assertEqual(parser.meta.get(key), value)
        self.assertEqual(parser.meta["og:image"], parser.meta["og:image:secure_url"])
        for key in ("og:url", "og:image", "og:image:secure_url", "twitter:image"):
            with self.subTest(url=key):
                self.assertTrue(parser.meta[key].startswith(self.site_url + "/"))
                self.assertTrue(parser.meta[key].startswith("https://"))
        metadata = " ".join(parser.meta.values())
        for private_value in ("+255712345678", "TEST-CUSTOMER-KEY", "-6.812345", "39.289876"):
            self.assertNotIn(private_value, metadata)

    def test_anonymous_crawler_user_agents_get_home_without_cookie_or_redirect(self):
        agents = ("WhatsApp/2.24", "facebookexternalhit/1.1", "Twitterbot", "TelegramBot")
        for agent in agents:
            with self.subTest(user_agent=agent):
                response = self.client.get("/", HTTP_USER_AGENT=agent)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.cookies)
                head_response = self.client.head("/", HTTP_USER_AGENT=agent)
                self.assertEqual(head_response.status_code, 200)

    def test_staff_admin_and_api_responses_are_noindex_without_open_graph(self):
        for path in ("/staff/", "/admin/", "/api/public/config"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn("noindex", response.headers.get("X-Robots-Tag", ""))
                body = response.content.decode(errors="replace")
                self.assertNotIn("property=\"og:", body)
                if path == "/staff/" and "html" in response.headers.get("Content-Type", ""):
                    parser = _PageHeadParser()
                    parser.feed(body)
                    self.assertEqual(parser.meta.get("robots"), "noindex,nofollow")

    @override_settings(SITE_URL="https://preview.example")
    def test_robots_and_sitemap_only_expose_public_home(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        robots_text = robots.content.decode()
        self.assertIn("Allow: /", robots_text)
        for path in ("/staff/", "/api/", "/admin/"):
            self.assertIn(f"Disallow: {path}", robots_text)
        self.assertIn(f"Sitemap: {self.site_url}/sitemap.xml", robots_text)

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertEqual(sitemap["Content-Type"], "application/xml")
        self.assertEqual(sitemap.content.decode().count("<loc>"), 1)
        self.assertIn(f"<loc>{self.site_url}/</loc>", sitemap.content.decode())


class LinkPreviewImageTests(TestCase):
    def test_versioned_share_image_is_public_png_at_required_dimensions(self):
        response = self.client.get("/static/og/share-1200x630-v1.png", HTTP_HOST="localhost")
        content = b"".join(response.streaming_content) if response.streaming else response.content
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("Content-Type", "").startswith("image/png"))
        self.assertLess(len(content), 300 * 1024)
        self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(unpack(">II", content[16:24]), (1200, 630))


class PublicPrivacyTests(TestCase):
    def setUp(self):
        for name in ("Public Shop", "Private Shop"):
            business = CustomerBusiness.objects.create(
                public_ref="BU-" + name.replace(" ", "").upper(),
                customer_name="Private Customer Name",
                business_name=name,
                phone="+255712345678",
                status=CustomerBusiness.Status.SERVED,
            )
            BusinessLocation.objects.create(
                business=business, latitude=Decimal("-6.812345"), longitude=Decimal("39.289876")
            )
            Consent.objects.create(
                business=business,
                privacy_notice_version="test",
                location_processing=True,
                public_listing=name == "Public Shop",
            )
        DemandCell.objects.create(
            cell_id="small", geojson={"type": "Point", "coordinates": [39.2, -6.8]}, request_count=2
        )
        DemandCell.objects.create(
            cell_id="large", geojson={"type": "Point", "coordinates": [39.2, -6.8]}, request_count=3
        )
        self.client = APIClient()

    def test_public_endpoints_filter_and_scrub_sensitive_business_data(self):
        response = self.client.post("/api/public/shops", {"bbox": "39,-7,40,-6"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        item = response.data["items"][0]
        self.assertEqual(item["lat"], -6.812)
        encoded = str(response.data)
        for private_value in ("+255712345678", "Private Customer Name", "-6.812345", "39.289876"):
            self.assertNotIn(private_value, encoded)

    def test_public_demand_hides_cells_below_three(self):
        response = self.client.post("/api/public/demand-cells", {"bbox": "39,-7,40,-6"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["cellId"] for item in response.data["items"]], ["large"])


class SensitiveSearchTransportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.root = get_user_model().objects.create_superuser(
            username="query-privacy-root",
            email="query-privacy@example.test",
            password="safe-test-password",
        )
        self.client.force_authenticate(user=self.root)

    def test_sensitive_list_searches_use_post_bodies_without_query_strings(self):
        cases = (
            ("/api/public/shops", {"bbox": "39,-7,40,-6", "limit": 500}),
            ("/api/public/demand-cells", {"bbox": "39,-7,40,-6"}),
            ("/api/public/shops/search", {"q": "Private Customer Name"}),
            ("/api/provider-codes/verify", {"phone": "+255712345678", "code": "TEST-KEY"}),
            ("/api/admin/businesses", {"page": 1, "q": "Private Customer Name"}),
            (
                "/api/admin/provider-codes",
                {"action": "search", "page": 1, "q": "+255712345678"},
            ),
        )
        for path, body in cases:
            with self.subTest(path=path):
                response = self.client.post(path, body, format="json")
                self.assertNotEqual(response.status_code, 405)
                self.assertEqual(response.wsgi_request.META.get("QUERY_STRING", ""), "")

    def test_sensitive_search_endpoints_reject_get_query_parameters(self):
        cases = (
            "/api/public/shops?bbox=39%2C-7%2C40%2C-6",
            "/api/public/demand-cells?bbox=39%2C-7%2C40%2C-6",
            "/api/public/shops/search?q=Private%20Customer%20Name",
            "/api/provider-codes/verify?phone=%2B255712345678&code=TEST-KEY",
            "/api/admin/businesses?q=Private%20Customer%20Name",
            "/api/admin/provider-codes?q=%2B255712345678",
        )
        for path in cases:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 405)

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz$"])
    def test_healthz_is_empty_and_exempt_from_https_redirect(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")


class DuplicatePhoneCheckTests(TestCase):
    def test_pre_migration_duplicate_check_masks_phone_and_does_not_write(self):
        for reference in ("BU-DUPCHECK-A", "BU-DUPCHECK-B"):
            CustomerBusiness.objects.create(
                public_ref=reference,
                customer_name="Fixture Customer",
                business_name=reference,
                phone="+255700000001",
            )
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command("check_duplicate_customer_phones", stdout=output, stderr=output)

        self.assertIn("•••• 0001: 2 records", output.getvalue())
        self.assertNotIn("+255700000001", output.getvalue())
        self.assertEqual(CustomerBusiness.objects.filter(phone="+255700000001").count(), 2)


class CodeAttemptRetentionTests(TestCase):
    def test_prune_command_removes_old_rows_and_keeps_recent_rows(self):
        now = timezone.now()
        stale = CodeAttempt.objects.create(code_hash="a" * 64)
        recent = CodeAttempt.objects.create(code_hash="b" * 64)
        CodeAttempt.objects.filter(pk=stale.pk).update(created_at=now - timedelta(hours=25))
        output = StringIO()

        call_command("prune_code_attempts", stdout=output)

        self.assertFalse(CodeAttempt.objects.filter(pk=stale.pk).exists())
        self.assertTrue(CodeAttempt.objects.filter(pk=recent.pk).exists())
        self.assertIn("1", output.getvalue())

    def test_throttle_path_opportunistically_prunes_bounded_old_rows(self):
        stale = CodeAttempt.objects.create(code_hash="c" * 64)
        CodeAttempt.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        with patch("core.security.secrets.randbelow", return_value=0):
            self.assertFalse(code_attempts_throttled("SOME-OTHER-CODE"))

        self.assertFalse(CodeAttempt.objects.filter(pk=stale.pk).exists())


class DeploymentConfigurationTests(TestCase):
    def test_render_blueprint_targets_production_branch(self):
        import re
        from pathlib import Path

        render_config = (Path(__file__).resolve().parents[1] / "render.yaml").read_text()
        branch = re.search(r"(?m)^\s{4}branch:\s*([^\s#]+)", render_config)
        self.assertIsNotNone(branch)
        self.assertEqual(branch.group(1), "production")

    def test_csp_is_report_only_and_contains_expected_external_sources(self):
        response = APIClient().get("/")
        policy = response.headers.get("Content-Security-Policy-Report-Only", "")
        self.assertIn("https://unpkg.com", policy)
        self.assertIn("https://photon.komoot.io", policy)
        self.assertNotIn("Content-Security-Policy", response.headers)


class AccuracyLanguageTests(TestCase):
    def test_customer_copy_does_not_promise_guaranteed_gps_accuracy(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        customer_copy = (root / "index.html").read_text().lower()
        self.assertNotRegex(customer_copy, r"\b99\s*%")
        self.assertIn("reported accuracy is an estimate, not a guarantee", customer_copy)
        for path in (root / "SRS.md", root / "RELEASE" / "READINESS.md"):
            text = path.read_text().lower()
            # Prohibitions on guarantees are safe; affirmative promises are not.
            self.assertNotRegex(text, r"(?:gps|location|accuracy).{0,80}(?:is|will be) guaranteed")


class LocationSignalValidationTests(TestCase):
    def location_payload(self, **overrides):
        data = {
            "customerName": "Signal Test Customer",
            "businessName": "Signal Test Shop",
            "phone": "0712345678",
            "latitude": -6.8,
            "longitude": 39.2,
            "accuracyMeters": 20,
            "locationSource": "gps",
            "fixTimestamp": timezone.now().isoformat(),
            "pinOffsetMeters": 0,
            "pinMovedByHand": False,
            "consent": True,
            "confirmed": True,
            "publicListing": False,
        }
        data.update(overrides)
        return data

    def test_fresh_gps_fix_is_accepted_with_server_calculated_age(self):
        from .serializers import LocationSubmissionSerializer

        serializer = LocationSubmissionSerializer(data=self.location_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertGreaterEqual(serializer.validated_data["fixAgeSeconds"], 0)
        self.assertLessEqual(serializer.validated_data["fixAgeSeconds"], 2)

    def test_coordinates_outside_configured_service_region_are_rejected(self):
        from .serializers import LocationSubmissionSerializer

        serializer = LocationSubmissionSerializer(data=self.location_payload(latitude=-20))
        self.assertFalse(serializer.is_valid())
        self.assertIn("latitude", serializer.errors)

    def test_stale_fix_is_rejected(self):
        from datetime import timedelta

        from .serializers import LocationSubmissionSerializer

        stale = (timezone.now() - timedelta(seconds=601)).isoformat()
        serializer = LocationSubmissionSerializer(data=self.location_payload(fixTimestamp=stale))
        self.assertFalse(serializer.is_valid())
        self.assertIn("fixTimestamp", serializer.errors)

    def test_fix_timestamp_without_timezone_is_rejected(self):
        from .serializers import LocationSubmissionSerializer

        local_timestamp = timezone.now().replace(tzinfo=None).isoformat()
        serializer = LocationSubmissionSerializer(
            data=self.location_payload(fixTimestamp=local_timestamp)
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("fixTimestamp", serializer.errors)

    def test_future_skew_and_impossible_accuracy_are_rejected(self):
        from datetime import timedelta

        from .serializers import LocationSubmissionSerializer

        future = (timezone.now() + timedelta(minutes=2)).isoformat()
        for updates in ({"fixTimestamp": future}, {"accuracyMeters": 100001}):
            serializer = LocationSubmissionSerializer(data=self.location_payload(**updates))
            self.assertFalse(serializer.is_valid())

    def test_manual_pin_needs_no_gps_fix_and_is_low_confidence(self):
        from .models import BusinessLocation
        from .serializers import LocationSubmissionSerializer
        from .views import location_confidence

        serializer = LocationSubmissionSerializer(
            data=self.location_payload(
                accuracyMeters=None,
                locationSource="manual_pin",
                fixTimestamp=None,
                pinOffsetMeters=None,
                pinMovedByHand=True,
            )
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        location = BusinessLocation(
            source=BusinessLocation.Source.MANUAL,
            accuracy_m=None,
            fix_age_seconds=None,
            pin_offset_m=None,
            pin_moved_by_hand=True,
            team_verified=False,
        )
        self.assertEqual(location_confidence(location)["level"], "low")

    def test_confidence_uses_accuracy_age_offset_and_staff_verification(self):
        from .models import BusinessLocation
        from .views import location_confidence

        good = BusinessLocation(
            source=BusinessLocation.Source.GPS,
            accuracy_m=20,
            fix_age_seconds=10,
            pin_offset_m=5,
            pin_moved_by_hand=False,
            team_verified=False,
        )
        large_offset = BusinessLocation(
            source=BusinessLocation.Source.GPS,
            accuracy_m=20,
            fix_age_seconds=10,
            pin_offset_m=500,
            pin_moved_by_hand=True,
            team_verified=False,
        )
        verified = BusinessLocation(
            source=BusinessLocation.Source.MANUAL,
            accuracy_m=None,
            fix_age_seconds=None,
            pin_offset_m=None,
            pin_moved_by_hand=True,
            team_verified=True,
        )
        self.assertEqual(location_confidence(good)["level"], "high")
        self.assertEqual(location_confidence(large_offset)["level"], "low")
        self.assertIn("offset", location_confidence(large_offset)["message"].lower())
        self.assertEqual(location_confidence(verified)["level"], "high")

    def test_submission_persists_offset_and_capture_source_without_original_fix(self):
        from django.test import RequestFactory

        from .models import BusinessLocation
        from .serializers import LocationSubmissionSerializer
        from .services import record_submission

        serializer = LocationSubmissionSerializer(
            data=self.location_payload(
                locationSource="manual_pin", pinOffsetMeters=85, pinMovedByHand=True
            )
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        business = record_submission(
            data=serializer.validated_data,
            request=RequestFactory().post("/api/location-submissions"),
        )
        location = BusinessLocation.objects.get(business=business)
        self.assertEqual(location.source, BusinessLocation.Source.MANUAL)
        self.assertEqual(float(location.pin_offset_m), 85)
        self.assertTrue(location.pin_moved_by_hand)
        self.assertIsNotNone(location.fix_age_seconds)
        self.assertFalse(hasattr(location, "gps_latitude"))
        self.assertFalse(hasattr(location, "gps_longitude"))


class CustomerDuplicateRecoveryTests(TestCase):
    def test_duplicate_keeps_verification_session_for_corrected_retry(self):
        phone = "+255712345650"
        existing = CustomerBusiness.objects.create(
            public_ref="BU-DUP-RECOVERY",
            customer_name="Fake Customer",
            business_name="Fake Shop",
            phone=phone,
        )
        BusinessLocation.objects.create(
            business=existing,
            latitude=Decimal("-6.800000"),
            longitude=Decimal("39.200000"),
            source=BusinessLocation.Source.MANUAL,
        )
        code = "DUPERECOVERY1234"
        provider_code = ProviderCode.objects.create(
            code_hash=hash_value(code),
            target_phone_hash=hash_value("provider-phone:" + phone),
            expires_at=timezone.now() + timedelta(hours=1),
            reusable=False,
            legacy_phone_lookup=False,
        )
        client = APIClient()
        verified = client.post(
            "/api/provider-codes/verify", {"code": code, "phone": phone}, format="json"
        )
        self.assertEqual(verified.status_code, 200)
        token = verified.data["verificationToken"]
        payload = {
            "customerName": "Fake Customer", "businessName": "Fake Shop", "phone": phone,
            "latitude": -6.800010, "longitude": 39.200010, "accuracyMeters": None,
            "locationSource": "manual_pin", "consent": True, "confirmed": True,
            "publicListing": False,
        }
        duplicate = client.post(
            "/api/location-submissions", payload, format="json",
            HTTP_AUTHORIZATION="Bearer " + token,
            HTTP_IDEMPOTENCY_KEY="duplicate-recovery-first-key",
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data["error"]["code"], "duplicate")
        self.assertEqual(CustomerBusiness.objects.count(), 1)
        session = VerificationSession.objects.get(provider_code=provider_code)
        self.assertIsNone(session.used_at)
        event = AuditLog.objects.get(action="customer.submission_rejected")
        self.assertEqual(event.metadata, {"status": 409, "error_code": "duplicate"})
        self.assertNotIn(phone, str(event.metadata))

        payload["latitude"] = -6.801000
        retry = client.post(
            "/api/location-submissions", payload, format="json",
            HTTP_AUTHORIZATION="Bearer " + token,
            HTTP_IDEMPOTENCY_KEY="duplicate-recovery-second-key",
        )
        self.assertEqual(retry.status_code, 201, retry.data)
        self.assertEqual(CustomerBusiness.objects.count(), 2)
        session.refresh_from_db()
        self.assertIsNotNone(session.used_at)


class CustomerSubmissionMessageTests(TestCase):
    def test_duplicate_is_a_conflict_and_never_a_success_screen(self):
        from pathlib import Path
        html = (Path(__file__).resolve().parents[1] / "index.html").read_text()
        self.assertIn("This location is already on file.", html)
        self.assertIn("nothing new was submitted", html.lower())
        self.assertNotIn('showSuccessScreen(null, true, "already_on_file")', html)


class DuplicateDetectionPolicyTests(TestCase):
    def setUp(self):
        self.business = CustomerBusiness.objects.create(
            public_ref="BU-DUPLICATE-TEST",
            customer_name="Test Person",
            business_name="Same Shop",
            phone="+255712345600",
        )
        BusinessLocation.objects.create(
            business=self.business,
            latitude=Decimal("-6.800000"),
            longitude=Decimal("39.200000"),
            source=BusinessLocation.Source.GPS,
        )

    def test_same_phone_and_business_within_radius_is_duplicate(self):
        self.assertTrue(real_find_duplicate(
            phone="+255712345600", business_name="Same Shop",
            latitude=Decimal("-6.800010"), longitude=Decimal("39.200010")
        ))

    def test_different_phone_or_different_business_nearby_is_not_duplicate(self):
        for phone, name in (("+255712345601", "Same Shop"), ("+255712345600", "Other Shop")):
            with self.subTest(phone=phone, business=name):
                self.assertFalse(real_find_duplicate(
                    phone=phone, business_name=name,
                    latitude=Decimal("-6.800010"), longitude=Decimal("39.200010")
                ))

    def test_rejected_neighbor_does_not_block_but_served_neighbor_does(self):
        self.business.status = CustomerBusiness.Status.REJECTED
        self.business.save(update_fields=["status"])
        kwargs = dict(phone="+255712345600", business_name="Same Shop",
                      latitude=Decimal("-6.800010"), longitude=Decimal("39.200010"))
        self.assertFalse(real_find_duplicate(**kwargs))
        self.business.status = CustomerBusiness.Status.SERVED
        self.business.save(update_fields=["status"])
        self.assertTrue(real_find_duplicate(**kwargs))

    @override_settings(LOCATION_DUPLICATE_RADIUS_M=5)
    def test_duplicate_radius_is_configurable(self):
        self.assertFalse(real_find_duplicate(
            phone="+255712345600", business_name="Same Shop",
            latitude=Decimal("-6.800100"), longitude=Decimal("39.200100")
        ))


class AssignedFieldTeamJourneyTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="field_team")
        self.user = get_user_model().objects.create_user(
            username="field-member", email="field@example.test", password="safe-test-password"
        )
        self.user.groups.add(self.group)
        self.assigned = self.create_business("BU-FIELD-ASSIGNED", assigned_to=self.user)
        self.other = self.create_business("BU-FIELD-OTHER")
        self.client = APIClient()
        self.client.force_login(self.user)
        session = self.client.session
        session["mfa_verified_user_id"] = str(self.user.pk)
        session.save()

    def create_business(self, reference, assigned_to=None):
        business = CustomerBusiness.objects.create(
            public_ref=reference,
            customer_name="Field Test Customer",
            business_name="Field Test Business",
            phone="+255712345670",
            assigned_to=assigned_to,
        )
        BusinessLocation.objects.create(
            business=business,
            latitude=Decimal("-6.8"),
            longitude=Decimal("39.2"),
            accuracy_m=Decimal("20"),
            source=BusinessLocation.Source.GPS,
            fix_age_seconds=10,
            pin_offset_m=Decimal("0"),
        )
        Consent.objects.create(
            business=business, privacy_notice_version="test", location_processing=True
        )
        return business

    def test_field_team_sees_only_assigned_jobs_and_cannot_open_another(self):
        response = self.client.post("/api/admin/businesses", {}, format="json")
        self.assertEqual(
            [row["reference"] for row in response.data["items"]], ["BU-FIELD-ASSIGNED"]
        )
        denied = self.client.get(f"/api/admin/businesses/{self.other.pk}")
        self.assertEqual(denied.status_code, 404)

    def test_arrival_check_returns_distance_and_audits_without_storing_position(self):
        response = self.client.post(
            f"/api/admin/businesses/{self.assigned.pk}/arrival-check",
            {
                "latitude": -6.8001,
                "longitude": 39.2,
                "accuracyMeters": 10,
                "fixTimestamp": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.data["distanceMeters"], 11.1, delta=1)
        event = AuditLog.objects.get(action="location.arrival_checked")
        self.assertEqual(event.object_id, str(self.assigned.pk))
        self.assertNotIn("-6.8001", str(event.metadata))
        self.assertNotIn("39.2", str(event.metadata))

    def test_arrival_check_rejects_unassigned_jobs(self):
        response = self.client.post(
            f"/api/admin/businesses/{self.other.pk}/arrival-check",
            {
                "latitude": -6.8,
                "longitude": 39.2,
                "accuracyMeters": 10,
                "fixTimestamp": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_field_team_can_correct_only_an_assigned_pin(self):
        response = self.client.patch(
            f"/api/admin/businesses/{self.assigned.pk}",
            {"correctedLatitude": -6.81, "correctedLongitude": 39.21},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["teamVerified"])
        denied = self.client.patch(
            f"/api/admin/businesses/{self.assigned.pk}",
            {"phone": "0712345678"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

    def test_field_team_cannot_list_assignable_accounts(self):
        response = self.client.get("/api/admin/assignable-staff")
        self.assertEqual(response.status_code, 403)

    def test_field_team_cannot_create_visit_records(self):
        response = self.client.post(
            f"/api/admin/businesses/{self.assigned.pk}/visits",
            {"visitDate": timezone.localdate().isoformat(), "team": "Field", "outcome": "Arrived"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_dispatcher_can_assign_jobs_to_field_team_member(self):
        dispatcher_group, _ = Group.objects.get_or_create(name="dispatcher")
        dispatcher = get_user_model().objects.create_user(
            username="dispatcher", password="safe-test-password"
        )
        dispatcher.groups.add(dispatcher_group)
        client = APIClient()
        client.force_login(dispatcher)
        session = client.session
        session["mfa_verified_user_id"] = str(dispatcher.pk)
        session.save()
        accounts = client.get("/api/admin/assignable-staff")
        self.assertEqual(accounts.status_code, 200)
        self.assertIn(
            {"id": self.user.pk, "username": "field-member", "role": "field_team"},
            accounts.data["items"],
        )
        assigned = client.patch(
            f"/api/admin/businesses/{self.other.pk}",
            {"assignee": self.user.pk},
            format="json",
        )
        self.assertEqual(assigned.status_code, 200)
        self.other.refresh_from_db()
        self.assertEqual(self.other.assigned_to_id, self.user.pk)


class PublicAssetIntegrityTests(TestCase):
    def test_public_leaflet_assets_are_pinned_and_integrity_protected(self):
        from pathlib import Path

        html = (Path(__file__).resolve().parents[1] / "index.html").read_text()
        for asset in ("leaflet.css", "leaflet.js"):
            tag = next(
                (
                    line
                    for line in html.splitlines()
                    if "leaflet@1.9.4" in line and asset.split(".")[0] in line
                ),
                "",
            )
            self.assertIn('integrity="sha256-', tag)
            self.assertIn("crossorigin", tag)


class CustomerFlowTests(TestCase):
    def test_legacy_nonreusable_key_submission_is_idempotent_and_single_use(self):
        code = "ABCD2345EFGH6789"
        ProviderCode.objects.create(
            code_hash=hash_value(code),
            target_phone_hash=hash_value("provider-phone:+255712345678"),
            expires_at=timezone.now() + timedelta(hours=1),
            max_uses=1,
        )
        client = APIClient()
        verified = client.post(
            "/api/provider-codes/verify", {"code": code, "phone": "0712345678"}, format="json"
        )
        self.assertEqual(verified.status_code, 200)
        token = verified.data["verificationToken"]
        payload = {
            "customerName": "Test Person",
            "businessName": "Test Store",
            "phone": "0712345678",
            "latitude": -6.812345,
            "longitude": 39.289876,
            "accuracyMeters": 25,
            "consent": True,
            "confirmed": True,
            "publicListing": False,
        }
        headers = {
            "HTTP_AUTHORIZATION": "Bearer " + token,
            "HTTP_IDEMPOTENCY_KEY": "test-idempotency-key-0001",
        }
        first = client.post("/api/location-submissions", payload, format="json", **headers)
        repeated = client.post("/api/location-submissions", payload, format="json", **headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(first.data, repeated.data)
        self.assertEqual(CustomerBusiness.objects.count(), 1)

    def test_invalid_codes_have_identical_public_response(self):
        client = APIClient()
        one = client.post(
            "/api/provider-codes/verify",
            {"code": "NOTACODE00000000", "phone": "0712345678"},
            format="json",
        )
        two = client.post(
            "/api/provider-codes/verify",
            {"code": "BADCODE000000000", "phone": "0712345678"},
            format="json",
        )
        self.assertEqual(one.status_code, two.status_code)
        self.assertEqual(one.data, two.data)

    def test_phone_and_code_must_match(self):
        code = "ABCD2345EFGH6789"
        ProviderCode.objects.create(
            code_hash=hash_value(code),
            target_phone_hash=hash_value("provider-phone:+255712345678"),
            expires_at=timezone.now() + timedelta(hours=1),
            max_uses=1,
        )
        response = APIClient().post(
            "/api/provider-codes/verify", {"code": code, "phone": "0755123456"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"valid": False})

    def test_new_customer_key_verification_is_audited_without_customer_values(self):
        code = "AUDIT-NEW-CUSTOMER"
        phone = "+255712345671"
        ProviderCode.objects.create(
            code_hash=hash_value(code),
            target_phone_hash=hash_value("provider-phone:" + phone),
            target_phone_last4=phone[-4:],
            reusable=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        response = APIClient().post(
            "/api/provider-codes/verify", {"phone": phone, "code": code}, format="json"
        )
        self.assertTrue(response.data["valid"])
        event = AuditLog.objects.get(action="customer.key_verified")
        self.assertEqual(event.object_type, "ProviderCode")
        self.assertNotIn(phone, str(event.metadata))
        self.assertNotIn(code, str(event.metadata))

    def test_failed_staff_login_audit_stores_reason_only(self):
        response = APIClient().post(
            "/api/auth/login",
            {"email": "not-a-user@example.test", "password": "never-log-this"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        event = AuditLog.objects.get(action="auth.login_failed")
        self.assertEqual(event.metadata, {"reason": "credentials_or_role"})
        self.assertNotIn("never-log-this", str(event.metadata))

    def test_reusable_key_repeats_until_expiry_or_revocation(self):
        phone, raw = "+255712345672", "REUSABLE-LIFECYCLE"
        code = ProviderCode.objects.create(
            code_hash=hash_value(raw),
            target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        client = APIClient()
        self.assertTrue(
            client.post(
                "/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json"
            ).data["valid"]
        )
        self.assertTrue(
            client.post(
                "/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json"
            ).data["valid"]
        )
        code.status = ProviderCode.Status.REVOKED
        code.save(update_fields=["status"])
        self.assertEqual(
            client.post(
                "/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json"
            ).data,
            {"valid": False},
        )

    def test_expired_key_is_rejected(self):
        phone, raw = "+255712345673", "EXPIRED-LIFECYCLE"
        ProviderCode.objects.create(
            code_hash=hash_value(raw),
            target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = APIClient().post(
            "/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json"
        )
        self.assertEqual(response.data, {"valid": False})

    def test_customer_can_update_profile_with_reusable_key(self):
        phone, raw = "+255712345678", "PROFILE-UPDATE-KEY"
        ProviderCode.objects.create(
            code_hash=hash_value(raw),
            target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        business = CustomerBusiness.objects.create(
            public_ref="BU-PROFILE-UPDATE",
            customer_name="Before Name",
            business_name="Before Shop",
            phone=phone,
        )
        BusinessLocation.objects.create(
            business=business, latitude=Decimal("-6.8"), longitude=Decimal("39.2")
        )
        Consent.objects.create(
            business=business, privacy_notice_version="test", location_processing=True
        )
        client = APIClient()
        verify = client.post(
            "/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json"
        )
        self.assertTrue(verify.data["valid"])
        response = client.put(
            "/api/customer/profile",
            {
                "customerName": "After Name",
                "businessName": "After Shop",
                "phone": phone,
                "latitude": -6.81,
                "longitude": 39.21,
                "accuracyMeters": 30,
                "consent": True,
                "confirmed": True,
                "publicListing": False,
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer " + verify.data["verificationToken"],
            HTTP_IDEMPOTENCY_KEY="profile-update-regression-001",
        )
        self.assertEqual(response.status_code, 200)
        business.refresh_from_db()
        self.assertEqual(business.customer_name, "After Name")
        self.assertEqual(business.location.latitude, Decimal("-6.810000"))
        event = AuditLog.objects.get(action="customer.profile_updated", object_id=str(business.pk))
        self.assertEqual(
            set(event.metadata["changed_fields"]),
            {"customer_name", "business_name", "location", "public_listing"},
        )


@skipUnless(
    connection.vendor == "postgresql", "Advisory-lock concurrency regression requires PostgreSQL"
)
class ConcurrentSubmissionTests(TransactionTestCase):
    reset_sequences = True

    def test_near_simultaneous_same_phone_submissions_create_only_one_business(self):
        phone = "+255712345679"
        tokens = ("first-test-token", "second-test-token")
        for index, token in enumerate(tokens):
            code = ProviderCode.objects.create(
                code_hash=hash_value(f"unused-test-code-{index}"),
                target_phone_hash=hash_value("provider-phone:" + phone),
                expires_at=timezone.now() + timedelta(minutes=10),
            )
            VerificationSession.objects.create(
                provider_code=code,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=timezone.now() + timedelta(minutes=5),
            )

        check_barrier = Barrier(2)

        def synchronized_duplicate_check(**kwargs):
            duplicate = real_find_duplicate(**kwargs)
            try:
                check_barrier.wait(timeout=1)
            except BrokenBarrierError:
                pass
            return duplicate

        def submit(token, key):
            close_old_connections()
            try:
                response = APIClient().post(
                    "/api/location-submissions",
                    {
                        "customerName": "Regression Test",
                        "businessName": "Regression Shop",
                        "phone": phone,
                        "latitude": -6.812345,
                        "longitude": 39.289876,
                        "accuracyMeters": 20,
                        "consent": True,
                        "confirmed": True,
                        "publicListing": False,
                    },
                    format="json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
                return response.status_code
            finally:
                close_old_connections()

        with patch("core.views.find_duplicate", side_effect=synchronized_duplicate_check):
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(
                    executor.map(
                        lambda item: submit(*item),
                        zip(
                            tokens, ("concurrent-submission-key-01", "concurrent-submission-key-02")
                        ),
                    )
                )

        self.assertEqual(sorted(statuses), [201, 409])
        self.assertEqual(CustomerBusiness.objects.filter(phone=phone).count(), 1)


class StaffMFATests(TestCase):
    def setUp(self):
        throttle_patch = patch("core.throttles.StaffLoginThrottle.allow_request", return_value=True)
        throttle_patch.start()
        self.addCleanup(throttle_patch.stop)
        self.user = get_user_model().objects.create_superuser(
            username="mfa-root",
            email="mfa-root@example.test",
            password="safe-test-password",
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def password_login(self):
        csrf = self.client.get("/api/auth/csrf").data["csrfToken"]
        return self.client.post(
            "/api/auth/login",
            {"email": self.user.email, "password": "safe-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )

    def mfa_post(self, path, data):
        csrf = self.client.get("/api/auth/csrf").data["csrfToken"]
        return self.client.post(path, data, format="json", HTTP_X_CSRFTOKEN=csrf)

    @staticmethod
    def current_code(device, *, at=None):
        generator = TOTP(device.bin_key, device.step, device.t0, device.digits)
        generator.time = time.time() if at is None else at
        return f"{generator.token():0{device.digits}d}"

    def enroll(self):
        login_response = self.password_login()
        self.assertTrue(login_response.data.get("mfaEnrollmentRequired"))
        enrollment_response = self.mfa_post("/api/auth/mfa/enroll", {})
        self.assertEqual(enrollment_response.status_code, 200)
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        response = self.mfa_post(
            "/api/auth/mfa/confirm", {"code": self.current_code(device)}
        )
        self.assertEqual(response.status_code, 200)
        return device, response.data["recoveryCodes"]

    def test_staff_password_login_requires_mfa_enrollment_and_blocks_staff_data(self):
        response = self.password_login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("mfaEnrollmentRequired"))
        self.assertFalse(response.data.get("authenticated", False))
        denied = self.client.post("/api/admin/businesses", {}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_mfa_enrollment_provides_qr_and_manual_key(self):
        self.password_login()
        csrf = self.client.get("/api/auth/csrf").data["csrfToken"]
        response = self.client.post(
            "/api/auth/mfa/enroll", {}, format="json", HTTP_X_CSRFTOKEN=csrf
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["secret"])
        self.assertTrue(response.data["otpauthUrl"].startswith("otpauth://totp/"))
        self.assertTrue(response.data["qrSvg"].startswith("data:image/svg+xml;base64,"))

    def test_expired_totp_code_is_rejected(self):
        device, _ = self.enroll()
        self.client.logout()
        login_response = self.password_login()
        self.assertTrue(login_response.data["mfaRequired"])
        stale_code = self.current_code(device, at=time.time() - 300)
        response = self.mfa_post("/api/auth/mfa/verify", {"code": stale_code})
        self.assertEqual(response.status_code, 401)
        event = AuditLog.objects.get(action="auth.mfa_failed")
        self.assertEqual(event.metadata, {"reason": "totp_invalid"})
        self.assertNotIn(stale_code, str(event.metadata))

    def test_wrong_totp_locks_out_challenge(self):
        device, _ = self.enroll()
        self.client.logout()
        self.password_login()
        for _ in range(5):
            response = self.mfa_post("/api/auth/mfa/verify", {"code": "000000"})
        self.assertEqual(response.status_code, 401)
        state = self.user.mfa_failure_state
        self.assertIsNotNone(state.locked_until)
        valid_code = self.current_code(device)
        locked_response = self.mfa_post("/api/auth/mfa/verify", {"code": valid_code})
        self.assertEqual(locked_response.status_code, 401)

    def test_recovery_code_is_hashed_single_use_and_audited(self):
        _, codes = self.enroll()
        self.assertEqual(len(codes), 10)
        row = StaffMFARecoveryCode.objects.filter(user=self.user).first()
        self.assertIsNotNone(row)
        self.assertNotEqual(row.code_hash, codes[0])
        self.assertTrue(check_password(codes[0], row.code_hash))
        self.client.logout()
        self.password_login()
        first = self.mfa_post("/api/auth/mfa/recovery", {"code": codes[0]})
        self.assertEqual(first.status_code, 200)
        self.assertIsNotNone(StaffMFARecoveryCode.objects.get(pk=row.pk).used_at)
        self.client.logout()
        self.password_login()
        second = self.mfa_post("/api/auth/mfa/recovery", {"code": codes[0]})
        self.assertEqual(second.status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="auth.mfa_succeeded").exists())

    def test_owner_reenrollment_fails_closed_without_configured_owner(self):
        _, _ = self.enroll()
        response = self.mfa_post(
            f"/api/admin/staff-users/{self.user.pk}/mfa-reenroll", {}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(TOTPDevice.objects.filter(user=self.user, confirmed=True).exists())

    def test_configured_recovery_owner_can_reset_staff_mfa_with_audit(self):
        self.enroll()
        with override_settings(MFA_RECOVERY_OWNER_EMAIL=self.user.email.lower()):
            response = self.mfa_post(
                f"/api/admin/staff-users/{self.user.pk}/mfa-reenroll", {}
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="auth.mfa_reenrolled_by_owner").exists()
        )

    def test_verified_staff_can_regenerate_recovery_codes(self):
        _, old_codes = self.enroll()
        device = TOTPDevice.objects.get(user=self.user, confirmed=True)
        next_step = (int(time.time()) // 30 + 1) * 30 + 1
        response = self.mfa_post(
            "/api/auth/mfa/recovery/regenerate",
            {"code": self.current_code(device, at=next_step)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recoveryCodes"]), 10)
        current_hashes = list(
            StaffMFARecoveryCode.objects.filter(user=self.user, used_at__isnull=True).values_list(
                "code_hash", flat=True
            )
        )
        self.assertFalse(
            any(check_password(code, hashed) for code in old_codes for hashed in current_hashes)
        )


class StaffPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = CustomerBusiness.objects.create(
            public_ref="BU-STAFFTEST",
            customer_name="A Customer",
            business_name="A Shop",
            phone="+255712345678",
        )
        BusinessLocation.objects.create(
            business=self.business,
            latitude=Decimal("-6.8"),
            longitude=Decimal("39.2"),
            accuracy_m=Decimal("28"),
        )
        Consent.objects.create(
            business=self.business, privacy_notice_version="test", location_processing=True
        )

    def test_anonymous_denied_and_dispatcher_cannot_export(self):
        self.assertEqual(self.client.post("/api/admin/businesses", {}, format="json").status_code, 403)
        self.assertTrue(
            AuditLog.objects.filter(
                action="auth.authorization_denied", object_type="StaffEndpoint"
            ).exists()
        )
        self.assertContains(self.client.get("/staff/"), "Staff sign in")
        dispatcher_group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="dispatcher", password="safe-test-password"
        )
        user.groups.add(dispatcher_group)
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.post("/api/admin/businesses", {}, format="json").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/export.csv").status_code, 403)

    def test_staff_home_has_dispatch_dashboard(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="dispatch-home", password="safe-test-password"
        )
        user.groups.add(group)
        self.client.force_login(user)
        session = self.client.session
        session["mfa_verified_user_id"] = str(user.pk)
        session.save()
        self.assertContains(self.client.get("/staff/"), "Dispatch")

    def test_django_admin_requires_superuser_even_for_other_staff(self):
        staff_user = get_user_model().objects.create_user(
            username="nonroot-admin",
            email="nonroot@example.test",
            password="safe-test-password",
            is_staff=True,
        )
        staff_user.groups.add(Group.objects.get_or_create(name="admin")[0])
        self.client.force_login(staff_user)
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        root = get_user_model().objects.create_superuser(
            username="root-site", email="root-site@example.test", password="safe-test-password"
        )
        self.client.force_login(root)
        session = self.client.session
        session["mfa_verified_user_id"] = str(root.pk)
        session.save()
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_pin_correction_is_audited_and_used_for_navigation(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="dispatch2", password="safe-test-password"
        )
        user.groups.add(group)
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/admin/businesses/{self.business.pk}",
            {"correctedLatitude": -6.81, "correctedLongitude": 39.21},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latitude"], -6.81)
        self.assertIn("-6.810000,39.210000", response.data["navigationLinks"]["googleMaps"])
        self.assertTrue(
            AuditLog.objects.filter(
                action="location.corrected", object_id=str(self.business.pk)
            ).exists()
        )
        event = AuditLog.objects.get(action="business.updated", object_id=str(self.business.pk))
        self.assertEqual(event.metadata, {"changed_fields": ["location"]})

    def test_superuser_staff_listing_is_audited(self):
        user = get_user_model().objects.create_superuser(
            username="auditor-root", email="root-audit@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get("/api/admin/staff-users").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="staff.users_listed", actor=user).exists())

    def test_staff_phone_hash_updates_when_customer_phone_changes(self):
        self.business.phone = "+255712345670"
        self.business.save(update_fields=["phone"])
        self.business.refresh_from_db()
        self.assertEqual(
            self.business.phone_hash, hash_value("provider-phone:" + self.business.phone)
        )

    def test_provider_key_history_is_limited_to_issuer(self):
        ProviderCode.objects.create(
            code_hash=hash_value("OWNED-CODE-123456"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            target_phone_last4=self.business.phone[-4:],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        provider_group, _ = Group.objects.get_or_create(name="service_provider")
        provider = get_user_model().objects.create_user(
            username="limited-provider", password="safe-test-password"
        )
        provider.groups.add(provider_group)
        self.client.force_authenticate(user=provider)
        response = self.client.post("/api/admin/provider-codes", {"action": "search"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_superuser_can_issue_reusable_customer_key(self):
        root = get_user_model().objects.create_superuser(
            username="key-issuer-root",
            email="key-issuer@example.test",
            password="safe-test-password",
        )
        self.client.force_authenticate(user=root)
        response = self.client.post(
            "/api/admin/provider-codes",
            {
                "phone": "0712345678",
                "label": "Regression account",
                "expiresAt": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["reusable"])
        self.assertTrue(ProviderCode.objects.get(pk=response.data["id"]).reusable)

    def test_provider_cannot_revoke_another_providers_key(self):
        provider_group, _ = Group.objects.get_or_create(name="service_provider")
        owner = get_user_model().objects.create_user(
            username="key-owner", password="safe-test-password"
        )
        owner.groups.add(provider_group)
        other = get_user_model().objects.create_user(
            username="key-outsider", password="safe-test-password"
        )
        other.groups.add(provider_group)
        code = ProviderCode.objects.create(
            code_hash=hash_value("OTHER-OWNER-CODE"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            expires_at=timezone.now() + timedelta(hours=1),
            created_by=owner,
        )
        self.client.force_authenticate(user=other)
        response = self.client.post(f"/api/admin/provider-codes/{code.pk}/revoke")
        self.assertEqual(response.status_code, 403)
        code.refresh_from_db()
        self.assertEqual(code.status, ProviderCode.Status.ACTIVE)
        self.assertTrue(
            AuditLog.objects.filter(
                action="auth.authorization_denied", object_type="ProviderCode"
            ).exists()
        )

    def test_dashboard_code_history_has_confirmed_revoke_action(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "templates" / "staff" / "dashboard.html"
        ).read_text()
        self.assertIn("data-revoke-code", source)
        self.assertIn("/admin/provider-codes/${button.dataset.revokeCode}/revoke", source)
        self.assertIn("window.confirm('Revoke this customer key?", source)

    def test_key_generation_prevents_native_submit_and_renders_before_history_refresh(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "templates" / "staff" / "dashboard.html"
        ).read_text()
        start = source.index("form.addEventListener('submit'")
        handler = source[start : source.index("</script>", start)]
        self.assertIn("event.preventDefault()", handler)
        self.assertLess(
            handler.index("result.hidden = false"), handler.index("provider-codes-updated")
        )
        self.assertNotIn("location.reload", handler)

    def test_staff_endpoint_role_matrix_for_directory_export_codes_and_audit(self):
        User = get_user_model()
        roles = {}
        for username, role in (
            ("matrix-dispatch", "dispatcher"),
            ("matrix-admin", "admin"),
            ("matrix-provider", "service_provider"),
        ):
            user = User.objects.create_user(username=username, password="safe-test-password")
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
            roles[role] = user
        assistant = roles["admin"]
        own_code = ProviderCode.objects.create(
            code_hash=hash_value("MATRIX-OWN-CODE"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            expires_at=timezone.now() + timedelta(hours=1),
            created_by=roles["service_provider"],
        )
        root = User.objects.create_superuser(
            username="matrix-root", email="matrix-root@example.test", password="safe-test-password"
        )

        def status(user, method, path):
            client = APIClient()
            if user is not None:
                client.force_authenticate(user=user)
            if method == "get" and path == "/api/admin/businesses":
                return client.post(path, {}, format="json").status_code
            if method == "get" and path == "/api/admin/provider-codes":
                return client.post(path, {"action": "search"}, format="json").status_code
            return getattr(client, method)(path).status_code

        anonymous = None
        self.assertIn(status(anonymous, "get", "/api/admin/businesses"), (401, 403))
        for role in ("dispatcher", "admin"):
            self.assertEqual(status(roles[role], "get", "/api/admin/businesses"), 200)
            self.assertEqual(
                status(roles[role], "get", f"/api/admin/businesses/{self.business.pk}"), 200
            )
        self.assertEqual(status(roles["service_provider"], "get", "/api/admin/businesses"), 403)
        self.assertEqual(status(assistant, "get", "/api/admin/staff-users"), 403)
        self.assertEqual(status(root, "get", "/api/admin/staff-users"), 200)
        self.assertEqual(status(roles["dispatcher"], "get", "/api/admin/export.csv"), 403)
        self.assertEqual(status(assistant, "get", "/api/admin/export.csv"), 200)
        self.assertEqual(status(roles["dispatcher"], "get", "/api/admin/provider-codes"), 403)
        self.assertEqual(status(assistant, "get", "/api/admin/provider-codes"), 200)
        self.assertEqual(status(roles["service_provider"], "get", "/api/admin/provider-codes"), 200)
        self.assertEqual(status(roles["dispatcher"], "get", "/api/admin/audit-log"), 403)
        self.assertEqual(status(assistant, "get", "/api/admin/audit-log"), 200)
        self.assertEqual(
            status(
                roles["service_provider"], "post", f"/api/admin/provider-codes/{own_code.pk}/revoke"
            ),
            200,
        )

    def test_superuser_can_create_staff_assistant(self):
        root = get_user_model().objects.create_superuser(
            username="staff-creator",
            email="staff-creator@example.test",
            password="safe-test-password",
        )
        self.client.force_authenticate(user=root)
        response = self.client.post(
            "/api/admin/staff-users",
            {
                "username": "new-assistant",
                "email": "assistant@example.test",
                "password": "a-safe-temp-password-553!",
                "role": "admin",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            get_user_model()
            .objects.get(username="new-assistant")
            .groups.filter(name="admin")
            .exists()
        )

    def test_csv_export_escapes_formula_leading_values(self):
        self.business.customer_name = '=HYPERLINK("https://bad.example")'
        self.business.save(update_fields=["customer_name"])
        root = get_user_model().objects.create_superuser(
            username="csv-root", email="csv-root@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=root)
        response = self.client.get("/api/admin/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=HYPERLINK", response.content.decode())

    def test_withdrawing_public_consent_removes_public_shop(self):
        self.business.status = CustomerBusiness.Status.SERVED
        self.business.consent.public_listing = True
        self.business.save(update_fields=["status"])
        self.business.consent.save(update_fields=["public_listing"])
        root = get_user_model().objects.create_superuser(
            username="consent-root",
            email="consent-root@example.test",
            password="safe-test-password",
        )
        self.client.force_authenticate(user=root)
        response = self.client.post("/api/public/shops", {"bbox": "39,-7,40,-6"}, format="json")
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            self.client.patch(
                f"/api/admin/businesses/{self.business.pk}", {"publicListing": False}, format="json"
            ).status_code,
            200,
        )
        response = self.client.post("/api/public/shops", {"bbox": "39,-7,40,-6"}, format="json")
        self.assertEqual(response.data["items"], [])

    def test_login_rejects_ambiguous_case_insensitive_email(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        for username in ("ambiguous-one", "ambiguous-two"):
            user = get_user_model().objects.create_user(
                username=username, email="duplicate@example.test", password="safe-test-password"
            )
            user.groups.add(group)
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/auth/csrf")
        token = csrf.data["csrfToken"]
        response = client.post(
            "/api/auth/login",
            {"email": "DUPLICATE@example.test", "password": "safe-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            AuditLog.objects.filter(
                action="auth.login_failed", metadata={"reason": "credentials_or_role"}
            ).exists()
        )

    def test_login_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            "/api/auth/login",
            {"email": "staff@example.test", "password": "not-used"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            AuditLog.objects.filter(
                action="auth.login_failed", metadata={"reason": "csrf"}
            ).exists()
        )

    def test_phone_change_rebinds_live_keys_and_audits_field_names(self):
        old_phone, new_phone = "+255712345678", "+255712345677"
        raw_key = "CHANGE-KEY-12345"
        ProviderCode.objects.create(
            code_hash=hash_value(raw_key),
            target_phone_hash=hash_value("provider-phone:" + old_phone),
            target_phone_last4=old_phone[-4:],
            expires_at=timezone.now() + timedelta(hours=1),
            max_uses=3,
        )
        revoked_raw_key = "REVOKED-KEY-12345"
        ProviderCode.objects.create(
            code_hash=hash_value(revoked_raw_key),
            target_phone_hash=hash_value("provider-phone:" + old_phone),
            target_phone_last4=old_phone[-4:],
            expires_at=timezone.now() + timedelta(hours=1),
            status=ProviderCode.Status.REVOKED,
            max_uses=3,
        )
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="phone-editor", password="safe-test-password"
        )
        user.groups.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            f"/api/admin/businesses/{self.business.pk}", {"phone": new_phone}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        code = ProviderCode.objects.get(code_hash=hash_value(raw_key))
        self.assertEqual(code.target_phone_hash, hash_value("provider-phone:" + new_phone))
        self.assertEqual(code.target_phone_last4, new_phone[-4:])
        revoked = ProviderCode.objects.get(code_hash=hash_value(revoked_raw_key))
        self.assertEqual(revoked.target_phone_hash, hash_value("provider-phone:" + old_phone))
        event = AuditLog.objects.get(
            action="business.phone_changed", object_id=str(self.business.pk)
        )
        self.assertEqual(
            event.metadata,
            {
                "changed_fields": ["phone"],
                "ambiguous_legacy_keys_revoked": 0,
                "legacy_keys_bound": 1,
            },
        )
        old_login = APIClient().post(
            "/api/provider-codes/verify", {"phone": old_phone, "code": raw_key}, format="json"
        )
        new_login = APIClient().post(
            "/api/provider-codes/verify", {"phone": new_phone, "code": raw_key}, format="json"
        )
        self.assertEqual(old_login.data, {"valid": False})
        self.assertTrue(new_login.data["valid"])

    def test_customer_phone_hash_is_index_value_and_code_history_links_without_phone_scan(self):
        self.assertEqual(
            self.business.phone_hash, hash_value("provider-phone:" + self.business.phone)
        )
        raw_key = "INDEXED-HISTORY-KEY"
        ProviderCode.objects.create(
            code_hash=hash_value(raw_key),
            target_phone_hash=self.business.phone_hash,
            target_phone_last4=self.business.phone[-4:],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        admin = get_user_model().objects.create_superuser(
            username="index-admin", email="index-admin@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=admin)
        response = self.client.post("/api/admin/provider-codes", {"action": "search"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["customerName"], self.business.customer_name)
        self.assertEqual(response.data["items"][0]["phone"], self.business.phone)
        self.assertTrue(
            AuditLog.objects.filter(action="provider_code.list_viewed", actor=admin).exists()
        )

    def test_phone_hash_updates_when_customer_phone_changes(self):
        self.business.phone = "+255712345670"
        self.business.save(update_fields=["phone"])
        self.business.refresh_from_db()
        self.assertEqual(
            self.business.phone_hash, hash_value("provider-phone:" + self.business.phone)
        )

    def test_staff_phone_edit_succeeds_with_postgresql_locking(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="postgres-phone-editor", password="safe-test-password"
        )
        user.groups.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            f"/api/admin/businesses/{self.business.pk}",
            {"phone": "+255712345676"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.business.refresh_from_db()
        self.assertEqual(self.business.phone, "+255712345676")

    def test_staff_phone_change_allows_shared_phone_and_only_rebinds_its_profile_key(self):
        other = CustomerBusiness.objects.create(
            public_ref="BU-OTHERPHONE",
            customer_name="Other Customer",
            business_name="Other Shop",
            phone="+255712345670",
        )
        BusinessLocation.objects.create(
            business=other, latitude=Decimal("-6.81"), longitude=Decimal("39.21")
        )
        own_key = ProviderCode.objects.create(
            code_hash=hash_value("own-profile-phone-edit-key"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            target_phone_last4=self.business.phone[-4:],
            business=self.business,
            legacy_phone_lookup=False,
            expires_at=timezone.now() + timedelta(days=1),
            reusable=True,
        )
        other_key = ProviderCode.objects.create(
            code_hash=hash_value("other-profile-phone-edit-key"),
            target_phone_hash=hash_value("provider-phone:" + other.phone),
            target_phone_last4=other.phone[-4:],
            business=other,
            legacy_phone_lookup=False,
            expires_at=timezone.now() + timedelta(days=1),
            reusable=True,
        )
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(
            username="duplicate-phone-editor", password="safe-test-password"
        )
        user.groups.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            f"/api/admin/businesses/{self.business.pk}",
            {"phone": other.phone},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.phone, other.phone)
        own_key.refresh_from_db()
        other_key.refresh_from_db()
        self.assertEqual(own_key.target_phone_hash, hash_value("provider-phone:" + other.phone))
        self.assertEqual(other_key.target_phone_hash, hash_value("provider-phone:" + other.phone))
        self.assertEqual(own_key.business_id, self.business.pk)
        self.assertEqual(other_key.business_id, other.pk)


class DashboardCustomerDataFlowTests(TestCase):
    def test_new_and_returning_customer_locations_appear_in_staff_list_and_detail(self):
        phone = "+255755555551"
        raw_code = "FLOW-TEST-CUSTOMER-KEY"
        ProviderCode.objects.create(
            code_hash=hash_value(raw_code),
            target_phone_hash=hash_value("provider-phone:" + phone),
            target_phone_last4=phone[-4:],
            expires_at=timezone.now() + timedelta(hours=2),
            reusable=True,
        )
        public_client = APIClient()
        verification = public_client.post(
            "/api/provider-codes/verify",
            {"phone": phone, "code": raw_code},
            format="json",
        )
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.data["valid"])

        def location_payload(latitude, business_name):
            return {
                "customerName": "Flow Test Customer",
                "businessName": business_name,
                "phone": phone,
                "latitude": latitude,
                "longitude": 39.289876,
                "accuracyMeters": 20,
                "locationSource": "gps",
                "fixTimestamp": timezone.now().isoformat(),
                "consent": True,
                "confirmed": True,
                "publicListing": False,
            }

        submitted = public_client.post(
            "/api/location-submissions",
            location_payload(-6.812345, "First Flow Shop"),
            format="json",
            HTTP_AUTHORIZATION="Bearer " + verification.data["verificationToken"],
            HTTP_IDEMPOTENCY_KEY="flow-submit-idempotency-1",
        )
        self.assertEqual(submitted.status_code, 201, submitted.data)
        business = CustomerBusiness.objects.get(public_ref=submitted.data["reference"])

        group, _ = Group.objects.get_or_create(name="dispatcher")
        staff_user = get_user_model().objects.create_user(
            username="flow-dispatcher", password="safe-test-password"
        )
        staff_user.groups.add(group)
        staff_client = APIClient()
        staff_client.force_login(staff_user)
        session = staff_client.session
        session["mfa_verified_user_id"] = str(staff_user.pk)
        session.save()

        def assert_staff_location(expected_latitude, expected_business_name):
            listing = staff_client.post("/api/admin/businesses", {}, format="json")
            self.assertEqual(listing.status_code, 200, listing.data)
            row = next(item for item in listing.data["items"] if item["id"] == str(business.pk))
            self.assertEqual(row["businessName"], expected_business_name)
            self.assertAlmostEqual(row["latitude"], expected_latitude, places=5)
            detail = staff_client.get(f"/api/admin/businesses/{business.pk}")
            self.assertEqual(detail.status_code, 200, detail.data)
            self.assertAlmostEqual(detail.data["originalLatitude"], expected_latitude, places=5)

        assert_staff_location(-6.812345, "First Flow Shop")

        returning_verification = public_client.post(
            "/api/provider-codes/verify",
            {"phone": phone, "code": raw_code},
            format="json",
        )
        self.assertEqual(returning_verification.status_code, 200)
        self.assertEqual(
            returning_verification.data["existingCustomer"]["reference"], business.public_ref
        )
        updated = public_client.put(
            "/api/customer/profile",
            location_payload(-6.814444, "Updated Flow Shop"),
            format="json",
            HTTP_AUTHORIZATION="Bearer " + returning_verification.data["verificationToken"],
            HTTP_IDEMPOTENCY_KEY="flow-profile-idempotency-1",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["reference"], submitted.data["reference"])
        self.assertEqual(CustomerBusiness.objects.count(), 1)
        assert_staff_location(-6.814444, "Updated Flow Shop")

    def test_recent_update_order_is_default_created_order_is_optional_and_pages_clamp(self):
        older = CustomerBusiness.objects.create(
            public_ref="BU-ORDER-OLD",
            customer_name="Older Customer",
            business_name="Older Shop",
            phone="+255755555561",
            created_at=timezone.now() - timedelta(days=10),
        )
        newer = CustomerBusiness.objects.create(
            public_ref="BU-ORDER-NEW",
            customer_name="Newer Customer",
            business_name="Newer Shop",
            phone="+255755555562",
            created_at=timezone.now() - timedelta(days=1),
        )
        for business in (older, newer):
            BusinessLocation.objects.create(
                business=business,
                latitude=Decimal("-6.8"),
                longitude=Decimal("39.2"),
            )
            Consent.objects.create(
                business=business,
                privacy_notice_version="test",
                location_processing=True,
            )
        older.updated_at = timezone.now()
        older.save(update_fields=["updated_at"])
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(username="order-dispatcher")
        user.groups.add(group)
        client = APIClient()
        client.force_authenticate(user=user)

        recent = client.post("/api/admin/businesses", {}, format="json")
        created = client.post(
            "/api/admin/businesses", {"sort": "newest_created"}, format="json"
        )
        clamped = client.post(
            "/api/admin/businesses", {"page": 500}, format="json"
        )

        self.assertEqual(recent.status_code, 200)
        self.assertEqual(recent.data["items"][0]["id"], str(older.pk))
        self.assertIn("updatedAt", recent.data["items"][0])
        self.assertEqual(created.data["items"][0]["id"], str(newer.pk))
        self.assertEqual(clamped.data["count"], 2)
        self.assertEqual(clamped.data["pages"], 1)
        self.assertEqual(clamped.data["page"], 1)
        self.assertEqual(len(clamped.data["items"]), 2)

    def test_staff_list_and_detail_distinguish_mfa_and_role_scope(self):
        business = CustomerBusiness.objects.create(
            public_ref="BU-MATRIX-FLOW",
            customer_name="Matrix Customer",
            business_name="Matrix Shop",
            phone="+255755555552",
        )
        BusinessLocation.objects.create(
            business=business, latitude=Decimal("-6.8"), longitude=Decimal("39.2")
        )
        Consent.objects.create(
            business=business, privacy_notice_version="test", location_processing=True
        )
        role_groups = {
            "admin": "admin",
            "dispatcher": "dispatcher",
            "provider": "service_provider",
            "field_assigned": "field_team",
            "field_unassigned": "field_team",
        }
        clients = {}
        for label, group_name in role_groups.items():
            user = get_user_model().objects.create_user(
                username=f"matrix-{label}", password="safe-test-password"
            )
            user.groups.add(Group.objects.get_or_create(name=group_name)[0])
            if label == "field_assigned":
                business.assigned_to = user
            client = APIClient()
            client.force_login(user)
            clients[label] = (client, user)
        business.save(update_fields=["assigned_to"])
        root = get_user_model().objects.create_superuser(
            username="matrix-flow-root", email="matrix-flow-root@example.test", password="test"
        )
        clients["superuser"] = (APIClient(), root)
        clients["superuser"][0].force_login(root)

        for label, (client, user) in clients.items():
            for path, method, data in (
                ("/api/admin/businesses", "post", {}),
                (f"/api/admin/businesses/{business.pk}", "get", None),
            ):
                without_mfa = getattr(client, method)(path, data, format="json") if data is not None else getattr(client, method)(path)
                self.assertEqual(without_mfa.status_code, 403, label)
                import json

                self.assertEqual(json.loads(without_mfa.content)["error"]["code"], "mfa_required", label)

            session = client.session
            session["mfa_verified_user_id"] = str(user.pk)
            session.save()
            response = client.post("/api/admin/businesses", {}, format="json")
            detail = client.get(f"/api/admin/businesses/{business.pk}")
            if label in {"superuser", "admin", "dispatcher", "field_assigned"}:
                self.assertEqual(response.status_code, 200, label)
                self.assertEqual(detail.status_code, 200, label)
            elif label == "field_unassigned":
                self.assertEqual(response.status_code, 200, label)
                self.assertEqual(response.data["items"], [])
                self.assertEqual(detail.status_code, 404, label)
            else:
                self.assertEqual(response.status_code, 403, label)
                self.assertEqual(response.data["error"]["code"], "staff_role_required", label)
                self.assertEqual(detail.status_code, 403, label)


class DashboardListQueryCountTests(TestCase):
    def test_customer_list_query_count_stays_bounded_for_fifty_rows(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        businesses = [
            CustomerBusiness(
                public_ref=f"BU-QUERY-{index:03d}",
                customer_name=f"Query Customer {index}",
                business_name=f"Query Shop {index}",
                phone=f"+25575555{index:04d}",
            )
            for index in range(50)
        ]
        CustomerBusiness.objects.bulk_create(businesses)
        BusinessLocation.objects.bulk_create(
            [
                BusinessLocation(
                    business=business,
                    latitude=Decimal("-6.8"),
                    longitude=Decimal("39.2"),
                )
                for business in businesses
            ]
        )
        Consent.objects.bulk_create(
            [
                Consent(
                    business=business,
                    privacy_notice_version="test",
                    location_processing=True,
                )
                for business in businesses
            ]
        )
        user = get_user_model().objects.create_user(username="query-dispatcher")
        user.groups.add(Group.objects.get_or_create(name="dispatcher")[0])
        client = APIClient()
        client.force_authenticate(user=user)

        with CaptureQueriesContext(connection) as queries:
            response = client.post("/api/admin/businesses", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 50)
        self.assertLessEqual(len(queries), 12, f"The list ran {len(queries)} queries")


class DashboardErrorStateTests(TestCase):
    def test_dashboard_explains_staff_roles_errors_and_csrf_failure(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parents[1] / "templates" / "staff" / "dashboard.html"
        ).read_text()
        for message in (
            "Your two-step verification expired",
            "Your staff role cannot see the customer inbox",
            "The staff server is temporarily unavailable",
            "The network could not load customer records",
            "No jobs are assigned to your account",
            "Keys awaiting customer submission",
            "Last loaded",
        ):
            self.assertIn(message, html)
        self.assertIn("Role {{ staff_role }} · MFA verified", html)
        self.assertIn('id="sortOrder"', html)
        self.assertNotIn(
            ".catch(()=>{if(IS_PROVIDER)showView('codesView');else load()})", html
        )
