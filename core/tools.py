"""Helper tools: language detection, alert scan, geofencing, route planning."""
import math
from data.geofences import GEOFENCES

SCRIPTS = [("Hindi/Marathi", 0x900, 0x97F), ("Bengali", 0x980, 0x9FF), ("Punjabi", 0xA00, 0xA7F),
           ("Gujarati", 0xA80, 0xAFF), ("Odia", 0xB00, 0xB7F), ("Tamil", 0xB80, 0xBFF),
           ("Telugu", 0xC00, 0xC7F), ("Kannada", 0xC80, 0xCFF), ("Malayalam", 0xD00, 0xD7F)]
ALIASES = {"मुंबई": "mumbai", "मुंबई": "mumbai", "गोवा": "goa", "चेन्नई": "chennai", "कोलकाता": "kolkata",
           "विशाखापत्तनम": "visakhapatnam", "மும்பை": "mumbai", "சென்னை": "chennai", "கொச்சி": "kochi",
           "கோவா": "goa", "ముంబై": "mumbai", "చెన్నై": "chennai", "കൊച്ചി": "kochi", "മുംബൈ": "mumbai",
           "ചെന്നൈ": "chennai", "মুম্বাই": "mumbai", "চেন্নাই": "chennai", "কলকাতা": "kolkata",
           "મુંબઈ": "mumbai", "ગોવા": "goa", "ಮಂಗಳೂರು": "mangalore", "ಮುಂಬೈ": "mumbai"}


def detect_lang(q):
    for ch in q:
        for n, a, b in SCRIPTS:
            if a <= ord(ch) <= b:
                return n
    return "English"


def normalize(q):
    for k, v in ALIASES.items():
        q = q.replace(k, v)
    return q


def find_cities(q, cities):
    ql = q.lower()
    return [c for _, c in sorted((ql.find(c), c) for c in cities if c in ql)]


def scan_alerts(s):
    """Windows in the 72 h series where thresholds are crossed."""
    out = []
    for name, k, c, hi, u in [("Wave height", "wave", 1.5, 2.5, "m"), ("Wind", "wind_kmh", 30, 45, "km/h"),
                              ("Ocean current", "current", 0.8, 1.2, "m/s")]:
        v, n, i = s[k], len(s[k]), 0
        while i < n:
            if v[i] is not None and v[i] > c:
                j, pk = i, v[i]
                while j + 1 < n and v[j + 1] is not None and v[j + 1] > c:
                    j += 1
                    pk = max(pk, v[j])
                out.append({"type": name, "level": "high" if pk > hi else "caution", "from": s["time"][i],
                            "to": s["time"][j], "peak": round(pk, 2), "unit": u, "index": i})
                i = j + 1
            else:
                i += 1
    return sorted(out, key=lambda a: (a["level"] != "high", a["index"]))


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def _inside(lat, lon, poly):
    ins = False
    for i in range(len(poly)):
        (y1, x1), (y2, x2) = poly[i], poly[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def geofence_check(lat, lon):
    res = []
    for z in GEOFENCES:
        near = min(hav(lat, lon, p[0], p[1]) for p in z["coords"])
        res.append({"name": z["name"], "type": z["type"], "illustrative": z["illustrative"],
                    "inside": _inside(lat, lon, z["coords"]), "nearest_vertex_km": round(near)})
    return sorted(res, key=lambda z: (not z["inside"], z["nearest_vertex_km"]))[:3]


def idw(g, lat, lon, h, key):
    ws = vs = 0
    for p in g["points"]:
        v = p[key][h]
        if v is None:
            continue
        w = 1 / max((lat - p["lat"]) ** 2 + (lon - p["lon"]) ** 2, 1e-4)
        ws += w
        vs += w * v
    return vs / ws if ws else None


def plan_route(g, a, b, h, assess):
    """Pick the lowest-risk of 5 lateral offsets of the A->B line. Ignores land: illustrative."""
    dy, dx = b[0] - a[0], b[1] - a[1]
    nrm = math.hypot(dy, dx) or 1
    py, px = -dx / nrm, dy / nrm
    best = None
    for off in (0, -1, 1, -2, 2):
        pts, pen = [], 0
        for i in range(21):
            t = i / 20
            bl = off * 0.6 * math.sin(math.pi * t)
            la, lo = a[0] + t * dy + bl * py, a[1] + t * dx + bl * px
            wv, wd = idw(g, la, lo, h, "wave"), idw(g, la, lo, h, "windSpeedMs")
            r = assess(wv, None if wd is None else wd * 3.6)["score"]
            if any(_inside(la, lo, z["coords"]) for z in GEOFENCES):
                pen += 1000
            pts.append({"lat": round(la, 3), "lon": round(lo, 3), "risk": r})
        dist = sum(hav(pts[i]["lat"], pts[i]["lon"], pts[i + 1]["lat"], pts[i + 1]["lon"]) for i in range(20))
        rk = [p["risk"] for p in pts]
        cost = max(rk) * 2 + sum(rk) / 21 + dist / 50 + pen
        if best is None or cost < best[0]:
            best = (cost, {"waypoints": pts, "distance_km": round(dist), "max_risk": max(rk),
                           "mean_risk": round(sum(rk) / 21), "options_evaluated": 5, "avoids_demo_zones": pen == 0,
                           "notes": "Open-water estimate from forecast wave/wind; ignores coastline, depth and legal boundaries."})
    return best[1]
