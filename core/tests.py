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


class PublicAssetIntegrityTests(TestCase):
    def test_public_leaflet_assets_are_pinned_and_integrity_protected(self):
        from pathlib import Path

        html = (Path(__file__).resolve().parents[1] / "index.html").read_text()
        for asset in ("leaflet.css", "leaflet.js"):
            tag = next((line for line in html.splitlines() if "leaflet@1.9.4" in line and asset.split(".")[0] in line), "")
            self.assertIn("integrity=\"sha256-", tag)
            self.assertIn("crossorigin", tag)


class CustomerFlowTests(TestCase):
    def test_legacy_nonreusable_key_submission_is_idempotent_and_single_use(self):
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
        response = APIClient().post("/api/provider-codes/verify", {"phone": phone, "code": code}, format="json")
        self.assertTrue(response.data["valid"])
        event = AuditLog.objects.get(action="customer.key_verified")
        self.assertEqual(event.object_type, "ProviderCode")
        self.assertNotIn(phone, str(event.metadata))
        self.assertNotIn(code, str(event.metadata))

    def test_failed_staff_login_audit_stores_reason_only(self):
        response = APIClient().post("/api/auth/login", {"email": "not-a-user@example.test", "password": "never-log-this"}, format="json")
        self.assertEqual(response.status_code, 401)
        event = AuditLog.objects.get(action="auth.login_failed")
        self.assertEqual(event.metadata, {"reason": "credentials_or_role"})
        self.assertNotIn("never-log-this", str(event.metadata))

    def test_reusable_key_repeats_until_expiry_or_revocation(self):
        phone, raw = "+255712345672", "REUSABLE-LIFECYCLE"
        code = ProviderCode.objects.create(
            code_hash=hash_value(raw), target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True, expires_at=timezone.now() + timedelta(hours=1),
        )
        client = APIClient()
        self.assertTrue(client.post("/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json").data["valid"])
        self.assertTrue(client.post("/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json").data["valid"])
        code.status = ProviderCode.Status.REVOKED
        code.save(update_fields=["status"])
        self.assertEqual(client.post("/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json").data, {"valid": False})

    def test_expired_key_is_rejected(self):
        phone, raw = "+255712345673", "EXPIRED-LIFECYCLE"
        ProviderCode.objects.create(
            code_hash=hash_value(raw), target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True, expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = APIClient().post("/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json")
        self.assertEqual(response.data, {"valid": False})

    def test_customer_can_update_profile_with_reusable_key(self):
        phone, raw = "+255712345678", "PROFILE-UPDATE-KEY"
        code = ProviderCode.objects.create(
            code_hash=hash_value(raw), target_phone_hash=hash_value("provider-phone:" + phone),
            reusable=True, expires_at=timezone.now() + timedelta(hours=1),
        )
        business = CustomerBusiness.objects.create(
            public_ref="BU-PROFILE-UPDATE", customer_name="Before Name", business_name="Before Shop", phone=phone,
        )
        BusinessLocation.objects.create(business=business, latitude=Decimal("-6.8"), longitude=Decimal("39.2"))
        Consent.objects.create(business=business, privacy_notice_version="test", location_processing=True)
        client = APIClient()
        verify = client.post("/api/provider-codes/verify", {"phone": phone, "code": raw}, format="json")
        self.assertTrue(verify.data["valid"])
        response = client.put(
            "/api/customer/profile",
            {"customerName": "After Name", "businessName": "After Shop", "phone": phone,
             "latitude": -6.81, "longitude": 39.21, "accuracyMeters": 30,
             "consent": True, "confirmed": True, "publicListing": False},
            format="json", HTTP_AUTHORIZATION="Bearer " + verify.data["verificationToken"],
            HTTP_IDEMPOTENCY_KEY="profile-update-regression-001",
        )
        self.assertEqual(response.status_code, 200)
        business.refresh_from_db()
        self.assertEqual(business.customer_name, "After Name")
        self.assertEqual(business.location.latitude, Decimal("-6.810000"))
        event = AuditLog.objects.get(action="customer.profile_updated", object_id=str(business.pk))
        self.assertEqual(set(event.metadata["changed_fields"]), {"customer_name", "business_name", "location", "public_listing"})


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
        self.assertTrue(AuditLog.objects.filter(action="auth.authorization_denied", object_type="StaffEndpoint").exists())
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

    def test_django_admin_requires_superuser_even_for_other_staff(self):
        staff_user = get_user_model().objects.create_user(
            username="nonroot-admin", email="nonroot@example.test", password="safe-test-password", is_staff=True
        )
        staff_user.groups.add(Group.objects.get_or_create(name="admin")[0])
        self.client.force_login(staff_user)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        root = get_user_model().objects.create_superuser(
            username="root-site", email="root-site@example.test", password="safe-test-password"
        )
        self.client.force_login(root)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

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
        self.assertEqual(self.business.phone_hash, hash_value("provider-phone:" + self.business.phone))

    def test_provider_key_history_is_limited_to_issuer(self):
        ProviderCode.objects.create(
            code_hash=hash_value("OWNED-CODE-123456"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            target_phone_last4=self.business.phone[-4:],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        provider_group, _ = Group.objects.get_or_create(name="service_provider")
        provider = get_user_model().objects.create_user(username="limited-provider", password="safe-test-password")
        provider.groups.add(provider_group)
        self.client.force_authenticate(user=provider)
        response = self.client.get("/api/admin/provider-codes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_superuser_can_issue_reusable_customer_key(self):
        root = get_user_model().objects.create_superuser(
            username="key-issuer-root", email="key-issuer@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=root)
        response = self.client.post("/api/admin/provider-codes", {
            "phone": "0712345678", "label": "Regression account",
            "expiresAt": (timezone.now() + timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["reusable"])
        self.assertTrue(ProviderCode.objects.get(pk=response.data["id"]).reusable)

    def test_provider_cannot_revoke_another_providers_key(self):
        provider_group, _ = Group.objects.get_or_create(name="service_provider")
        owner = get_user_model().objects.create_user(username="key-owner", password="safe-test-password")
        owner.groups.add(provider_group)
        other = get_user_model().objects.create_user(username="key-outsider", password="safe-test-password")
        other.groups.add(provider_group)
        code = ProviderCode.objects.create(
            code_hash=hash_value("OTHER-OWNER-CODE"),
            target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            expires_at=timezone.now() + timedelta(hours=1), created_by=owner,
        )
        self.client.force_authenticate(user=other)
        response = self.client.post(f"/api/admin/provider-codes/{code.pk}/revoke")
        self.assertEqual(response.status_code, 403)
        code.refresh_from_db()
        self.assertEqual(code.status, ProviderCode.Status.ACTIVE)
        self.assertTrue(AuditLog.objects.filter(action="auth.authorization_denied", object_type="ProviderCode").exists())

    def test_dashboard_code_history_has_confirmed_revoke_action(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "templates" / "staff" / "dashboard.html").read_text()
        self.assertIn("data-revoke-code", source)
        self.assertIn("/admin/provider-codes/${button.dataset.revokeCode}/revoke", source)
        self.assertIn("window.confirm('Revoke this customer key?", source)

    def test_key_generation_prevents_native_submit_and_renders_before_history_refresh(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "templates" / "staff" / "dashboard.html").read_text()
        start = source.index("form.addEventListener('submit'")
        handler = source[start:source.index("</script>", start)]
        self.assertIn("event.preventDefault()", handler)
        self.assertLess(handler.index("result.hidden = false"), handler.index("provider-codes-updated"))
        self.assertNotIn("location.reload", handler)

    def test_staff_endpoint_role_matrix_for_directory_export_codes_and_audit(self):
        User = get_user_model()
        roles = {}
        for username, role in (("matrix-dispatch", "dispatcher"), ("matrix-admin", "admin"),
                               ("matrix-provider", "service_provider")):
            user = User.objects.create_user(username=username, password="safe-test-password")
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
            roles[role] = user
        assistant = roles["admin"]
        own_code = ProviderCode.objects.create(
            code_hash=hash_value("MATRIX-OWN-CODE"), target_phone_hash=hash_value("provider-phone:" + self.business.phone),
            expires_at=timezone.now() + timedelta(hours=1), created_by=roles["service_provider"],
        )
        root = User.objects.create_superuser(username="matrix-root", email="matrix-root@example.test", password="safe-test-password")

        def status(user, method, path):
            client = APIClient()
            if user is not None:
                client.force_authenticate(user=user)
            return getattr(client, method)(path).status_code

        anonymous = None
        self.assertIn(status(anonymous, "get", "/api/admin/businesses"), (401, 403))
        for role in ("dispatcher", "admin"):
            self.assertEqual(status(roles[role], "get", "/api/admin/businesses"), 200)
            self.assertEqual(status(roles[role], "get", f"/api/admin/businesses/{self.business.pk}"), 200)
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
        self.assertEqual(status(roles["service_provider"], "post", f"/api/admin/provider-codes/{own_code.pk}/revoke"), 200)

    def test_superuser_can_create_staff_assistant(self):
        root = get_user_model().objects.create_superuser(
            username="staff-creator", email="staff-creator@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=root)
        response = self.client.post("/api/admin/staff-users", {
            "username": "new-assistant", "email": "assistant@example.test",
            "password": "a-safe-temp-password-553!", "role": "admin",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(get_user_model().objects.get(username="new-assistant").groups.filter(name="admin").exists())

    def test_csv_export_escapes_formula_leading_values(self):
        self.business.customer_name = "=HYPERLINK(\"https://bad.example\")"
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
            username="consent-root", email="consent-root@example.test", password="safe-test-password"
        )
        self.client.force_authenticate(user=root)
        response = self.client.get("/api/public/shops", {"bbox": "39,-7,40,-6"})
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(self.client.patch(
            f"/api/admin/businesses/{self.business.pk}", {"publicListing": False}, format="json"
        ).status_code, 200)
        response = self.client.get("/api/public/shops", {"bbox": "39,-7,40,-6"})
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
            "/api/auth/login", {"email": "DUPLICATE@example.test", "password": "safe-test-password"},
            format="json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="auth.login_failed", metadata={"reason": "credentials_or_role"}).exists())

    def test_login_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post("/api/auth/login", {"email": "staff@example.test", "password": "not-used"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action="auth.login_failed", metadata={"reason": "csrf"}).exists())

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

    def test_customer_phone_hash_is_index_value_and_code_history_links_without_phone_scan(self):
        self.assertEqual(self.business.phone_hash, hash_value("provider-phone:" + self.business.phone))
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
        response = self.client.get("/api/admin/provider-codes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["customerName"], self.business.customer_name)
        self.assertEqual(response.data["items"][0]["phone"], self.business.phone)
        self.assertTrue(AuditLog.objects.filter(action="provider_code.list_viewed", actor=admin).exists())

    def test_phone_hash_updates_when_customer_phone_changes(self):
        self.business.phone = "+255712345670"
        self.business.save(update_fields=["phone"])
        self.business.refresh_from_db()
        self.assertEqual(self.business.phone_hash, hash_value("provider-phone:" + self.business.phone))

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
