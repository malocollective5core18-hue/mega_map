# 03 – Public Map and UI Specification

Base: existing single-file `index.html` (Leaflet, Esri satellite only, green #0f3d2e + amber accent). Preserve its look and the location-sharing flow.

## Screens
1. **Home map**: full-screen satellite map, top bar (logo, name, search), right controls (zoom, my location), bottom panel with "SHARE OFFICE LOCATION" and support buttons.
2. **Layer panel**: toggles "Shops we serve" (default on), "Areas of demand" (default on). New customers are never shown here.
3. **Shop popup**: business name, area/ward, "Served since <year>", no phone, no exact address.
4. **Demand cell popup**: "Several businesses here have asked for our service" (no counts below 3).
5. **Request service**: opens the existing flow, or WhatsApp/phone when the user lacks a code.
6. **Search**: by place (geocoder) and by business name (own API).

## Behaviour
- Load pins as the viewport changes (`GET /api/public/shops?bbox=`), cluster above ~50 pins, cap 500 per response.
- Marker styles: green = served shop, amber heat cells = demand.
- Only show the user's own position after they tap "My location".
- Satellite imagery has no labels, so add a label layer for place names (confirm provider licence) or rely on the search results.

## Quality
- Mobile-first, targets ≥ 48 px, portrait and landscape, reduced-motion support.
- Kiswahili first, English toggle; text in a single dictionary object.
- Keyboard and screen-reader support, visible focus, WCAG AA contrast.
- Show a clear message if tiles or API fail; page must not break.
- Initial load under 300 KB excluding tiles.
