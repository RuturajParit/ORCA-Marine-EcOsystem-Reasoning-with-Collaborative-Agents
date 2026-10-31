"""Geofence zones. ALL ENTRIES BELOW ARE ILLUSTRATIVE DEMOS - NOT LEGAL BOUNDARIES.
Replace with official IMBL / EEZ / MPA polygons (e.g. from PostGIS) before real use.
Coordinates are [lat, lon]."""
GEOFENCES = [
    {"name": "Demo restricted zone (Mumbai offshore)", "type": "restricted", "illustrative": True,
     "coords": [[18.5, 71.5], [18.5, 72.2], [19.2, 72.2], [19.2, 71.5]]},
    {"name": "Demo marine protected area (Goa offshore)", "type": "mpa", "illustrative": True,
     "coords": [[15.0, 72.6], [15.0, 73.1], [15.5, 73.1], [15.5, 72.6]]},
]
