import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import BrokenBarrierError, Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AuditLog, BusinessLocation, CodeAttempt, Consent, CustomerBusiness, DemandCell, ProviderCode, VerificationSession
from .security import code_attempts_throttled, hash_value
from .services import find_duplicate as real_find_duplicate


class PublicPrivacyTests(TestCase):
    def setUp(self):
        for name in ("Public Shop", "Private Shop"):
            business = CustomerBusiness.objects.create(
                public_ref="BU-" + name.replace(" ", "").upper(),
                customer_name="Private Customer Name", business_name=name,
                phone="+255712345678", status=CustomerBusiness.Status.SERVED,
            )
            BusinessLocation.objects.create(business=business, latitude=Decimal("-6.812345"), longitude=Decimal("39.289876"))
            Consent.objects.create(business=business, privacy_notice_version="test", location_processing=True, public_listing=name == "Public Shop")
        DemandCell.objects.create(cell_id="small", geojson={"type": "Point", "coordinates": [39.2, -6.8]}, request_count=2)
        DemandCell.objects.create(cell_id="large", geojson={"type": "Point", "coordinates": [39.2, -6.8]}, request_count=3)
        self.client = APIClient()

    def test_public_endpoints_filter_and_scrub_sensitive_business_data(self):
        response = self.client.get("/api/public/shops", {"bbox": "39,-7,40,-6"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        item = response.data["items"][0]
        self.assertEqual(item["lat"], -6.812)
        encoded = str(response.data)
        for private_value in ("+255712345678", "Private Customer Name", "-6.812345", "39.289876"):
            self.assertNotIn(private_value, encoded)

    def test_public_demand_hides_cells_below_three(self):
        response = self.client.get("/api/public/demand-cells", {"bbox": "39,-7,40,-6"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["cellId"] for item in response.data["items"]], ["large"])


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
        CodeAttempt.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=25))

        with patch("core.security.secrets.randbelow", return_value=0):
            self.assertFalse(code_attempts_throttled("SOME-OTHER-CODE"))

        self.assertFalse(CodeAttempt.objects.filter(pk=stale.pk).exists())


class DeploymentConfigurationTests(TestCase):
    def test_render_blueprint_targets_production_branch(self):
        from pathlib import Path
        import re

        render_config = (Path(__file__).resolve().parents[1] / "render.yaml").read_text()
        branch = re.search(r"(?m)^\s{4}branch:\s*([^\s#]+)", render_config)
        self.assertIsNotNone(branch)
        self.assertEqual(branch.group(1), "production")


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


class PublicAssetIntegrityTests(TestCase):
    def test_public_leaflet_assets_are_pinned_and_integrity_protected(self):
        from pathlib import Path

        html = (Path(__file__).resolve().parents[1] / "index.html").read_text()
        for asset in ("leaflet.css", "leaflet.js"):
            tag = next((line for line in html.splitlines() if "leaflet@1.9.4" in line and asset.split(".")[0] in line), "")
            self.assertIn("integrity=\"sha256-", tag)
            self.assertIn("crossorigin", tag)


class CustomerFlowTests(TestCase):
    def test_valid_code_submission_is_idempotent_and_single_use(self):
        code = "ABCD2345EFGH6789"
        ProviderCode.objects.create(code_hash=hash_value(code), target_phone_hash=hash_value("provider-phone:+255712345678"), expires_at=timezone.now() + timedelta(hours=1), max_uses=1)
        client = APIClient()
        verified = client.post("/api/provider-codes/verify", {"code": code, "phone": "0712345678"}, format="json")
        self.assertEqual(verified.status_code, 200)
        token = verified.data["verificationToken"]
        payload = {"customerName": "Test Person", "businessName": "Test Store", "phone": "0712345678", "latitude": -6.812345, "longitude": 39.289876, "accuracyMeters": 25, "consent": True, "confirmed": True, "publicListing": False}
        headers = {"HTTP_AUTHORIZATION": "Bearer " + token, "HTTP_IDEMPOTENCY_KEY": "test-idempotency-key-0001"}
        first = client.post("/api/location-submissions", payload, format="json", **headers)
        repeated = client.post("/api/location-submissions", payload, format="json", **headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(first.data, repeated.data)
        self.assertEqual(CustomerBusiness.objects.count(), 1)

    def test_invalid_codes_have_identical_public_response(self):
        client = APIClient()
        one = client.post("/api/provider-codes/verify", {"code": "NOTACODE00000000", "phone": "0712345678"}, format="json")
        two = client.post("/api/provider-codes/verify", {"code": "BADCODE000000000", "phone": "0712345678"}, format="json")
        self.assertEqual(one.status_code, two.status_code)
        self.assertEqual(one.data, two.data)

    def test_phone_and_code_must_match(self):
        code = "ABCD2345EFGH6789"
        ProviderCode.objects.create(code_hash=hash_value(code), target_phone_hash=hash_value("provider-phone:+255712345678"), expires_at=timezone.now() + timedelta(hours=1), max_uses=1)
        response = APIClient().post("/api/provider-codes/verify", {"code": code, "phone": "0755123456"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"valid": False})


@skipUnless(connection.vendor == "postgresql", "Advisory-lock concurrency regression requires PostgreSQL")
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
                statuses = list(executor.map(
                    lambda item: submit(*item),
                    zip(tokens, ("concurrent-submission-key-01", "concurrent-submission-key-02")),
                ))

        self.assertEqual(sorted(statuses), [201, 409])
        self.assertEqual(CustomerBusiness.objects.filter(phone=phone).count(), 1)


class StaffPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = CustomerBusiness.objects.create(public_ref="BU-STAFFTEST", customer_name="A Customer", business_name="A Shop", phone="+255712345678")
        BusinessLocation.objects.create(business=self.business, latitude=Decimal("-6.8"), longitude=Decimal("39.2"), accuracy_m=Decimal("28"))
        Consent.objects.create(business=self.business, privacy_notice_version="test", location_processing=True)

    def test_anonymous_denied_and_dispatcher_cannot_export(self):
        self.assertEqual(self.client.get("/api/admin/businesses").status_code, 403)
        self.assertContains(self.client.get("/staff/"), "Staff sign in")
        dispatcher_group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(username="dispatcher", password="safe-test-password")
        user.groups.add(dispatcher_group)
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get("/api/admin/businesses").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/export.csv").status_code, 403)

    def test_staff_home_has_dispatch_dashboard(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(username="dispatch-home", password="safe-test-password")
        user.groups.add(group)
        self.client.force_login(user)
        self.assertContains(self.client.get("/staff/"), "Dispatch")

    def test_pin_correction_is_audited_and_used_for_navigation(self):
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(username="dispatch2", password="safe-test-password")
        user.groups.add(group)
        self.client.force_authenticate(user=user)
        response = self.client.patch(f"/api/admin/businesses/{self.business.pk}", {"correctedLatitude": -6.81, "correctedLongitude": 39.21}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latitude"], -6.81)
        self.assertIn("-6.810000,39.210000", response.data["navigationLinks"]["googleMaps"])
        self.assertTrue(AuditLog.objects.filter(action="location.corrected", object_id=str(self.business.pk)).exists())

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
        user = get_user_model().objects.create_user(username="phone-editor", password="safe-test-password")
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
        event = AuditLog.objects.get(action="business.phone_changed", object_id=str(self.business.pk))
        self.assertEqual(event.metadata, {"changed_fields": ["phone"]})
        old_login = APIClient().post(
            "/api/provider-codes/verify", {"phone": old_phone, "code": raw_key}, format="json"
        )
        new_login = APIClient().post(
            "/api/provider-codes/verify", {"phone": new_phone, "code": raw_key}, format="json"
        )
        self.assertEqual(old_login.data, {"valid": False})
        self.assertTrue(new_login.data["valid"])

    def test_staff_phone_change_rejects_phone_used_by_another_business(self):
        other = CustomerBusiness.objects.create(
            public_ref="BU-OTHERPHONE",
            customer_name="Other Customer",
            business_name="Other Shop",
            phone="+255712345670",
        )
        BusinessLocation.objects.create(
            business=other, latitude=Decimal("-6.81"), longitude=Decimal("39.21")
        )
        group, _ = Group.objects.get_or_create(name="dispatcher")
        user = get_user_model().objects.create_user(username="duplicate-phone-editor", password="safe-test-password")
        user.groups.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            f"/api/admin/businesses/{self.business.pk}",
            {"phone": other.phone},
            format="json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "phone_in_use")
        self.business.refresh_from_db()
        self.assertEqual(self.business.phone, "+255712345678")
