# Assumptions and owner decisions

- The company operates in Tanzania and stores phone numbers in E.164 format. Local 10-digit mobile/landline inputs beginning with `0` normalize to `+255`.
- A provider code is single-use by default and its bearer verification token expires within 30 minutes.
- Approximate public coordinates are rounded to three decimal places (roughly 100 m latitude granularity); demand cells require at least three submissions.
- Dispatchers may view and edit customer records; admins control public listing consent, exports, provider codes and audit records.
- A GPS fix with no reported accuracy is considered manually placed for staff confidence display.
- **Needs owner decision:** Confirm the one-business-per-phone rule and the handling of legacy duplicate-phone records before applying a database uniqueness constraint. Staff phone edits currently reject a phone already used by another business; run `python manage.py check_duplicate_customer_phones` against a protected data copy before any uniqueness migration.
- **Secret rotation:** Customer-business and provider-code phone HMACs are keyed by `DJANGO_SECRET_KEY`. Rotation changes these digests; schedule a controlled rehash/recovery migration before changing the secret.
- **Staff security release gate:** MFA is not implemented. TOTP enrollment, recovery, reenrollment, and lockout must be completed before routine customer records are handled in production.

## Owner/legal decisions required before release

- Approve the privacy notice text/version and confirm its fit with Tanzania's Personal Data Protection Act, 2022.
- Choose retention periods for rejected, duplicate, submitted and served records and approve the anonymisation policy.
- Confirm the regions/wards used for reporting and the public-map area coverage.
- Decide whether admins alone may export and who may be assigned dispatch jobs.
- Approve company phone and WhatsApp numbers, operational MFA policy, and backup retention/access controls.
- Review Esri imagery and any future geocoding provider terms and data-processing arrangements.
