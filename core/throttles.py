from rest_framework.throttling import AnonRateThrottle


class PublicThrottle(AnonRateThrottle):
    scope = "public"


class VerifyThrottle(AnonRateThrottle):
    scope = "verify"


class SubmissionThrottle(AnonRateThrottle):
    scope = "submit"


class StaffLoginThrottle(AnonRateThrottle):
    scope = "staff_login"
