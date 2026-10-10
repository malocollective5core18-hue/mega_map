from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AuditLog, BusinessLocation, Consent, CustomerBusiness, DemandCell, ProviderCode
from .security import hash_value


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
