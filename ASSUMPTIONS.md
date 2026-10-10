# Assumptions and owner decisions

- The company operates in Tanzania and stores phone numbers in E.164 format. Local 10-digit mobile/landline inputs beginning with `0` normalize to `+255`.
- A provider code is single-use by default and its bearer verification token expires within 30 minutes.
- Approximate public coordinates are rounded to three decimal places (roughly 100 m latitude granularity); demand cells require at least three submissions.
- Dispatchers may view and edit customer records; admins control public listing consent, exports, provider codes and audit records.
- A GPS fix with no reported accuracy is considered manually placed for staff confidence display.

## Owner/legal decisions required before release

- Approve the privacy notice text/version and confirm its fit with Tanzania's Personal Data Protection Act, 2022.
- Choose retention periods for rejected, duplicate, submitted and served records and approve the anonymisation policy.
- Confirm the regions/wards used for reporting and the public-map area coverage.
- Decide whether admins alone may export and who may be assigned dispatch jobs.
- Approve company phone and WhatsApp numbers, operational MFA policy, and backup retention/access controls.
- Review Esri imagery and any future geocoding provider terms and data-processing arrangements.
