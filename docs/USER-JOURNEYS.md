# User journeys: Mauzosheet location and service platform

**Audit baseline:** branch `feature/user-journeys`, commit based on `fix/audit-defects` at `d26535e`.
**Evidence rule:** journey steps below describe current source behavior; missing behaviors are labeled **Gap** or **Planned**. Source references use repository paths and line numbers as inspected on 14 October 2026. Browser layout and real-device behavior are **Not tested** unless stated.

## Shared customer behavior

The public entry is `/` (`stocktaking/urls.py:31`). The page has a map, search, layer menu, **SHARE BUSINESS LOCATION**, support buttons, and a location-sharing dialog (`index.html:669-735`). Customer API requests use `/api/provider-codes/verify`, `/api/location-submissions`, and `/api/customer/profile` (`core/urls.py:10-12`). A verified key returns a short-lived token; the key itself may be reusable (`core/views.py:196-265`, `core/models.py:8-44`).

The customer form currently displays mainly English, with selected Kiswahili prompts, button labels, and success text; there is no language switch. It asks for the phone/key, name, business name, location, explicit confirmation, and optional public-listing consent (`index.html:722-845`). A capture started by customer tap uses `watchPosition` with high accuracy for up to about 15 seconds, keeps the best fix, shows an accuracy circle and reported radius, warns above the configured threshold, and asks the customer to stop if reported speed exceeds the movement threshold. Speed is used client-side only and is not sent or stored (`index.html:1350-1400`). Submission sends the fix timestamp, reported accuracy, source, final pin, offset and hand-moved flag. The server calculates and stores fix age; it does not store the original GPS coordinate or speed (`core/serializers.py:27-124`, `core/services.py:79-107`).

Location permission is requested only after a customer chooses **Endelea** or retries GPS in the location step. The browser may show its own permission prompt then. The watcher is stopped after completion, failure, cancellation, navigation away, or pagehide (`index.html:1207-1212,1258-1259,1350-1400,1576`). Poor readings remain usable after a warning; manual pin placement is accepted. The accuracy circle stays centered on the original fix while the final pin can be moved. The server stores only offset distance, not the original fix coordinate.

The service validates global coordinate range and a configurable broad Tanzania bounding rectangle, maximum reported accuracy, fix age, future skew, and consent/confirmation. The rectangle overlaps neighboring countries and is only a placeholder until the owner approves a real service boundary. Manual pins are accepted within configured bounds and receive Low confidence until field verification. Staff confidence uses source, accuracy, server-calculated age, offset and verified correction; large offsets are flagged, not blocked (`core/serializers.py:64-124`, `core/views.py:1055-1082`). Public config supplies adjustable warning thresholds for GPS accuracy and device-reported movement. Notice text is versioned as `2026-10-location-v1` and described in `PRIVACY-NOTICE.md`; owner/legal approval remains open.

## 1. New customer — first location submission

**Goal and trigger:** register one business location after receiving a provider-issued phone-bound key. **Entry:** `/` → **SHARE BUSINESS LOCATION** (`index.html:709-715`). **Preconditions:** active code for the entered phone; network; browser with JavaScript. Location permission is optional because the customer can place the pin manually.

1. **Public map.** The visitor sees the service summary, map, search, support controls, and the share action. Map layers start with satellite, served shops and demand selected (`index.html:687-715`, `index.html:694-697`). The customer opens the share dialog. No customer data is sent yet.
2. **Verify your service key.** English title and explanation; phone and service-key inputs; **Continue**, **Cancel**, and “Don't have a service provider code?” (`index.html:722-735`). The customer enters the company-supplied phone and key. Client-side messages: “Enter the customer phone number linked to this code.” and “Enter the full code you received from the company.” Invalid phone/key pairs use the generic “This code could not be verified. Check it and try again.” (`index.html:1264-1284`). Expired key: “This code has expired. Please request a new one.”; too many attempts: “Too many attempts. Please wait and try again.” Network/timeout/server errors use the exact messages in `index.html:1277-1305`.
3. **Your details.** For a phone with no existing record, the customer sees full name, business/shop name and verified phone (read-only), then **Continue**, **Back**, **Cancel** (`index.html:753-766`, `index.html:1308-1320`). Exact validation: “Enter your full name.”, “Enter your business or shop name.”, and “Enter a valid phone number, e.g. 0712 345 678 or +255712345678.” Phone is copied from the verified flow; user name and business name remain editable. The only new data is those profile fields.
4. **Eneo la biashara / location introduction.** Bilingual instruction says to be at the business; English help recommends standing outside with a sky view and keeping still. **Endelea** starts location capture; **Sitisha** opens cancellation; **Back** returns to details (`index.html:768-777`). On the Continue tap, the browser Geolocation API is called and the OS/browser can show its permission prompt (`index.html:1323-1362`). No location runs in the background.
5. **Confirm the pin.** Shows an area/landmark/bus-stand search field, matching places list, coordinates, reported accuracy, place label, **Retry GPS**, **Review**, and **Sitisha**. Photon receives the typed search text (`index.html:779-803`, `index.html:1030-1040`, `index.html:1145-1158`). The best observed estimate can be used; >30m is warned but not blocked. The customer can search, tap the map or drag the pin to the entrance. The page asks the customer to verify the entrance themselves. A manual move replaces the GPS accuracy with “not reported.” Search/tap/drag does not prove presence.
6. **Review.** Shows customer, business, phone, final coordinates, place and accuracy, location-processing notice, optional unchecked public-map consent, and the Kiswahili confirmation prompt; actions are **Thibitisha na Tuma**, **Rudi Urekebishe**, **Edit details**, **Sitisha** (`index.html:806-832`). Only public-listing consent is optional; submission confirmation and processing consent are required by the API (`core/serializers.py:55-58`). Review sends no data until submit.
7. **Sending / success.** The client posts a bearer token and idempotency key. Success shows business, reference and a confirmation; **Done** clears the draft, and WhatsApp support is available (`index.html:1374-1422`, `index.html:843-845`). The server returns a generated reference and records consent/audit metadata (`core/services.py:79-107`).

**Error/empty states:** map unavailable banner says “Map could not load. Check your internet connection and reload. You can still share your location below.” (`index.html:671-672`). No key navigates to a contact screen with **Contact Us on WhatsApp**, **Call Our Office**, **Back**, **Cancel** (`index.html:744-751`). Search empty/error copy is listed in the screen spec. Location denied: “Location permission was denied. Allow location in your browser settings and retry, or tap the map to place the pin.” No fix after timeout: “No GPS fix was received. Move outdoors, check location permission, then retry or place the pin on the map.” (`index.html:1336-1362`). Submit 422, 409, 5xx, timeout, and network paths are in the Bad Path journey below.

**Accessibility/responsive:** dialog uses dialog semantics, labelled fields, alert/status nodes, focus transfer and a tab loop (`index.html:717`, `index.html:1233-1240`, `index.html:1456-1464`). Search controls expose combobox/listbox roles. Screen-reader behavior and 360×640/390×844 whole-page overflow are **Not tested**. UI copy is not fully Kiswahili-first. The map requires an alternate pin interaction when touch dragging is difficult; tapping the map is available.

**Gaps:** browser/device permission and watcher lifecycle still require real-device/browser tests; full Kiswahili-first translation and language switch are not implemented; the region rectangle and retention/legal copy require owner approval. Whole-page overflow and 48px controls are not measured in a browser.

## 2. Returning customer — update profile/location

**Goal/trigger:** revise a saved business using the same reusable phone/key. **Entry/preconditions:** same public path as new customers; reusable active key bound to an existing phone record.

1. **Verify your service key:** same phone/key screen. Server verification returns the latest matching business profile and its stored location if found (`core/views.py:196-265`).
2. **Welcome back:** displays “Signed in as {name} · {business} ({phone}).” and **Review / edit business details**, **Close** (`index.html:737-742`, `index.html:1286-1303`). Customer chooses review/edit.
3. **Edit your details:** prefilled name/business/phone; verified phone read-only; name/business may be changed (`index.html:1308-1320`).
4. **Location intro and pin:** saved location is shown as a map pin. **Endelea** opens the location screen without requesting GPS when a saved pin exists; it explicitly says “Your saved location is selected. Review it on the map, move the pin if needed, or retry GPS.” **Retry GPS** is available (`index.html:1439-1446`). GPS permission appears only if customer taps Endelea for a new record or Retry GPS; the saved pin alone does not prompt.
5. **Review and submit:** same review screen; **Thibitisha na Tuma** sends `PUT /api/customer/profile`; server updates the newest matching phone record, location, and consent and audits changed fields (`index.html:1375-1405`, `core/views.py:400-555`). Success title: “Account details updated”; body: “Your business details and location have been updated.” (`index.html:1417-1421`).

Errors, keyboard behavior, and mobile fit match the new-customer flow. If multiple records are associated with a phone, current customer logic uses the newest record; product behavior for multiple businesses per phone is an owner decision. Accidental same-tab reload restores draft fields, location, token and consent while the client expiry remains valid (`index.html:1189-1231`); the server can still reject it as expired/used on submit.

## 3. Customer on a bad path

| Failure | Current screen/system behavior | Exact current user message or status |
|---|---|---|
| Wrong phone or key | Verification screen; generic response avoids identifying which value failed. | “This code could not be verified. Check it and try again.” (`index.html:1283`) |
| Expired/revoked/used-up key | Verification screen. | Expired: “This code has expired. Please request a new one.” Revoked/otherwise invalid: generic wrong-key message. API verification returns `{valid:false}` for inactive/expired/mismatched keys (`core/views.py:196-265`). |
| GPS permission denied | Location screen remains usable for manual pin. Browser permission prompt occurred after explicit capture action. | “Location permission was denied. Allow location in your browser settings and retry, or tap the map to place the pin.” (`index.html:1360-1362`) |
| GPS unavailable / denied / timeout | Error callback stops the watcher and distinguishes denied, unavailable, and timeout; map/manual route remains. | Exact message is selected in the `messages` object in `index.html` near location capture handler. Browser-level behavior is Not tested. |
| Poor accuracy | Best available fix is accepted with a configurable warning; it is not blocked. | Copy requests retry outdoors/near a window and asks the user to check and adjust the pin. Default warning threshold is 50m. |
| Network outage during key verify | Keeps verification form and can retry. | “Request timed out. Check your connection and retry.” / “Network error. Check your connection and retry.” (`index.html:1303-1305`) |
| Search service outage/no results | Search results panel remains with manual map route. | “Place search is unavailable. You can still tap the map to set the pin.” / “No matching places found. Try another area or landmark.” (`index.html:1153-1158`) |
| Verification session expired/invalid | Draft is cleared after submit receives 410; customer must start with key again. | “Your session expired. Please start again with your code.” (`index.html:1388-1390`) |
| Server validation 422 | Displays field errors where supplied. Serializer checks region, reported accuracy, timestamp freshness/skew, offset, profile, and required consent/confirmation. | Field-level messages come from the serializer and are mapped in `index.html` submit flow (`core/serializers.py:27-124`). |
| HTTP 409 duplicate or idempotency conflict | **Gap fixed in current source:** duplicate response is recognized separately; other conflicts remain errors and do not show success. | See `index.html` submit response handler and `core/views.py` duplicate/idempotency error codes. Runtime/browser behavior is Not tested. |
| 5xx / request timeout | Preserves the draft for retry; idempotency key is reused. | “Server error. Your location was not saved. Please retry.”, “Request timed out. Not sent. Retry.”, or “Network error. Not sent. Retry.” (`index.html:1402-1408`) |
| Accidental reload | `sessionStorage` restores step, name/business, verified phone/token, selected coordinates, idempotency key and public-listing choice until client expiry. It does not ask the server to revalidate until next request. | “Your in-progress details were restored. This draft is available in this tab until your verified session expires.” (`index.html:1192-1231`) |
| Map unavailable | Main map displays a warning but customer form remains accessible; cannot drag/tap a map pin. Search fallback may still return a map location but cannot visually confirm it. | Banner in `index.html:671-672`; no dedicated alternate coordinate entry is provided. |

**Gaps:** distinguish 409 conflict from duplicate acceptance; handle geolocation TIMEOUT and POSITION_UNAVAILABLE errors promptly; indicate when server has invalidated a restored session before final submit; browser-level retry/error and focus announcements need Playwright verification.

## 4. Public visitor

**Goal:** understand service, search a place or opted-in served business, view aggregate demand and contact the company to request access. **Entry:** `/`.

1. **Map/home:** visitor sees service description, map, area search, satellite/layer menu, map credit footer, **SHARE BUSINESS LOCATION**, **WhatsApp support**, **Call office** (`index.html:669-715`).
2. **Search area:** type at least 3 characters. Photon is queried with `countrycode=TZ`; suggestions can be selected to center the map. Statuses: “Searching nearby areas…”, “No matching areas found. Try another name.”, “Area suggestions are unavailable. You can still search and move the map.” Search text is sent to Photon (`index.html:1035-1112`).
3. **Shops we serve / Areas of demand:** layer menu checkboxes call public APIs (`index.html:691-700`, `index.html:935-979`). Shops endpoint filters for served + consent and rounds coordinates to 0.001 degrees, returns business name/area/public reference only. Demand endpoint hides counts; server only serves cells with a minimum aggregate count (`core/views.py:95-116`, `core/views.py:119-190`). Public endpoints do not serialize customer name or phone.
4. **Request access:** choose share, then “Don't have a service provider code?” → **Contact Us on WhatsApp** / **Call Our Office** (`index.html:734-751`). Contact destination comes from `/api/public/config`. If unset, exact messages are “WhatsApp number is not configured yet (COMPANY_WHATSAPP_NUMBER).” and “Office phone number is not configured yet (COMPANY_PHONE_NUMBER).” (`index.html:1177-1179`).

Keyboard: search exposes combobox/listbox roles; Escape closes suggestions. Layer labels are native checkboxes. Public full-page mobile fit and map layer accessibility are **Not tested**. No guaranteed service boundary is disclosed and no plain-language policy explains when/why the browser reads location until the sharing flow.

## 5. Dispatcher

**Goal:** review and manage customer records, contact/navigate, and correct pins after verification. **Entry:** `/staff/` → email/password then TOTP/recovery code. First login requires TOTP enrollment (QR/manual key), confirmation, and saving one-time recovery codes; later logins require TOTP or a recovery code (`templates/staff/login.html:12-20`, `core/views.py:635-810`). UI strings are currently English. MFA route enforcement is implemented in `core/middleware.py` and `core/mfa.py`.

1. **Staff sign in:** email, password, **Sign in**. First enrollment screen asks user to scan QR or enter manual key and enter authenticator code; recovery codes are shown once. Errors are announced in `#message` (`templates/staff/login.html:12-20,23-38`).
2. **Customer map/inbox:** dispatcher sees map/inbox table, search/filter/page controls and resizable panel. It requests `GET /api/admin/businesses`; loading/empty/error strings are rendered by dashboard JS (`templates/staff/dashboard.html:74-93,208-243`). Dispatcher can inspect records and open details.
3. **Details/edit:** shows contact/customer fields, status/notes, map pin, location confidence context, visit form and action links; updates permitted details by PATCH (`templates/staff/dashboard.html:224-239`, `core/views.py:400-685`). Exact field-by-field contents are listed in `docs/UI-SCREEN-SPEC.md`.
4. **Navigate/copy:** Google Maps driving/walking and other map links are generated from the selected navigation coordinates; coordinates are copyable in registered customers (`core/views.py:455-489`, `templates/staff/dashboard.html:214-238`).
5. **Pin correction:** dispatcher may set corrected coordinates in detail UI; API audits correction, and navigation uses corrected position only after `team_verified` is set (`core/models.py:131-191`, `core/views.py:587-685`).

**Gap:** a complete dispatch assignment/scheduling/outcome lifecycle and viewport/browser verification are still absent. Phone/desktop overflow and MFA browser flow are **Not tested**.

## 6. Service provider

**Goal:** issue reusable customer keys and manage only their own issuance history. **Entry:** `/staff/` sign in with MFA. On successful provider login, the dashboard opens **Customer login keys** rather than the customer map (`templates/staff/dashboard.html:90-100,255`).

1. Sign in with email/password + TOTP/recovery as above.
2. **Customer login keys:** enter customer phone, optional label, expiry, then **Generate reusable customer key**. Copy the secret from the one-time result; server persists only a hash. Provider history is searchable/filterable, and own key can be revoked after confirmation (`templates/staff/dashboard.html:90-93,110-196,245-246`; `core/views.py:967-1100`).
3. History API returns masked phone suffix/status/expiry/use count but not secret. Provider query is restricted to codes they issued (`core/views.py:967-1033`). Empty/loading states are within code table.

**Gap:** exact phone identity is not fully searchable when only last-four metadata exists; browser flows, key copy/share and mobile table fit are **Not tested**. Providers do not see customer directory.

## 7. Administrator and admin assistant

### Admin assistant

Admin assistant signs in with MFA and can use customer map, Registered customers, detail/edit, export, audit log, and customer-key history. Backend allows admin group access for customer data, export, audit, key history and public-listing changes; staff-account management is superuser-only (`core/views.py:561-623,867-1050`, `templates/staff/dashboard.html:73-106`). It cannot issue keys or create staff users. The user prompt groups staff account visibility with admin assistants; **Gap:** actual code hides registration of staff users from admins and API rejects them.

### Superuser / administrator

Superuser signs in with MFA. In addition to admin assistant functions, gets the admin-only navigation for registering admin assistants and service providers, issuing keys, and viewing audit/export; Django `/admin/` is limited to a Django superuser and MFA-verified session (`templates/staff/dashboard.html:94-106`, `core/views.py:608-623,867-965`, `core/admin.py:6-11`, `core/middleware.py:35-65`).

**Public listing:** admin PATCH may update consent `publicListing`; public shops endpoint includes only served records whose consent is true. No dedicated staff screen provides a consent-withdrawal explanation or customer notification (`core/views.py:95-116,587-685`).

## 8. Field team member

**Goal:** reach an assigned business, compare a one-time device position with its pin, then correct the pin after checking the entrance. **Entry:** `/staff/` → **My assigned jobs** after email/password + MFA. The field-team account is created by the superuser. The list and detail APIs restrict records to assignments.

1. Field team opens the assignment list and searches/paginates assigned customer jobs. Empty state says no matching customers. Selecting **Open** loads the assigned detail; unassigned IDs return 404.
2. Detail includes customer/business contact, confidence/source/accuracy context, and Google driving/walking and alternate map links. The field team does not see the general profile edit form or the provider/admin sections.
3. On tapping **Check my position against this pin**, the browser requests one high-accuracy position (maximum age zero, 15-second timeout). If denied, unavailable or timed out, a specific message asks the member to change permission/settings or retry. Success displays approximate distance and the device-reported accuracy. This check sends coordinates/time/accuracy transiently to the authorized server; the server validates bounds and freshness, returns distance, and audits a distance band only. It does not store staff coordinates.
4. After confirming the entrance, the member may save the map center as the corrected pin. This is limited to assigned records and audited with member/time. Other profile fields and visit creation are rejected; dispatch staff manage assignment and job status.

**Remaining gap:** assignment lifecycle and real device/browser behavior are not tested. A distance result is not proof of physical presence; no continuous tracking occurs.

## Accessibility and device behavior common to staff

Staff login has labelled form controls and native autocomplete. Dashboard uses semantic tables, labelled search/filter inputs, buttons, and keyboard arrows for the resize handle. Sidebar focus management, screen-reader complete review, target-size conformance, reduced-motion coverage, and actual 360×640/390×844 page overflow were not measured. Current interface strings are mostly English, not Kiswahili-first. Treat all phone/desktop fit claims as **Not tested** until browser runs and screenshots are available.
