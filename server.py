"""
ORCA API server  –  run:  uvicorn server:app --reload --port 8000
Open http://localhost:8000  (frontend is served from static/index.html)

GET  /api/health            service + NIM status
GET  /api/cities            known cities
GET  /api/grid              13x17 Indian-coast grid, 72 h forecast (cached 30 min)
GET  /api/point?lat=&lon=   hourly forecast + safety assessment for one point
POST /api/ask               {query, lat?, lon?} -> runs the LangGraph agents
"""
import os
import time
from datetime import date as _date, timedelta
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from data.cmems import SPECS, NOTES, fetch_layer
from data.open_meteo import fetch_sealevel, fetch_marine, fetch_weather, fetch_combined_point, _safe_float
from main import CITIES, resolve_location
from core.model_manager import ModelManager
from core.orchestrator import ORCAOrchestrator
from core.graph import build_graph
from agents.ocean_agent import OceanAgent
from agents.weather_agent import WeatherAgent
from agents.geospatial_agent import GeospatialAgent
from agents.analyst_agent import MarineAnalyst
from core.tools import (detect_lang, normalize, find_cities, scan_alerts, geofence_check,
                        idw, plan_route)
from data.geofences import GEOFENCES

app = FastAPI(title="ORCA Marine API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])

LATS = [6 + i * 1.5 for i in range(13)]
LONS = [68 + i * 1.5 for i in range(17)]
_cache = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def now_index(times):
    t0 = datetime.fromisoformat(times[0]).replace(tzinfo=timezone.utc)
    h = int((datetime.now(timezone.utc) - t0).total_seconds() // 3600)
    return max(0, min(len(times) - 1, h))


def assess(wave, wind_kmh):
    """Transparent rule engine (same thresholds as the original prototype)."""
    w, k = wave or 0, wind_kmh or 0
    if w > 2.5 or k > 45:
        level, label = "high", "High Risk"
    elif w > 1.5 or k > 30:
        level, label = "caution", "Caution"
    else:
        level, label = "safe", "Generally Safe"
    return {
        "level": level, "label": label,
        "score": round(min(100, max(w / 4, k / 60) * 100)),
        "reasons": [f"Wave height {w:.1f} m (caution >1.5, high >2.5)",
                    f"Wind {k:.0f} km/h (caution >30, high >45)"],
    }


# ------------------------------------------------------------------ grid
def _parse_date(d):
    if not d:
        return None
    try:
        dt = _date.fromisoformat(d)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    today = datetime.now(timezone.utc).date()
    if not today - timedelta(days=60) <= dt <= today + timedelta(days=7):
        raise HTTPException(400, "date must be within 60 days back and 7 days ahead")
    return dt.isoformat()


def _dates(d):
    return (None, None) if not d else (d, (_date.fromisoformat(d) + timedelta(days=2)).isoformat())


def start_index(times, d):
    return 12 if d and d != datetime.now(timezone.utc).date().isoformat() else now_index(times)


def _chunk(pairs, d=None):
    la = ",".join(str(p[0]) for p in pairs)
    lo = ",".join(str(p[1]) for p in pairs)
    sd, ed = _dates(d)
    m, w = fetch_marine(la, lo, 3, sd, ed), fetch_weather(la, lo, 3, sd, ed)
    return (m if isinstance(m, list) else [m]), (w if isinstance(w, list) else [w])


def build_grid(d=None):
    pairs = [(a, o) for a in LATS for o in LONS]
    chunks = [pairs[i:i + 40] for i in range(0, len(pairs), 40)]
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda c: _chunk(c, d), chunks))
    M = [x for r in res for x in r[0]]
    W = [x for r in res for x in r[1]]
    times = M[0]["hourly"]["time"]

    def col(d, k):
        return [_safe_float(v) for v in d.get("hourly", {}).get(k, [None] * len(times))]

    points = [{
        "lat": a, "lon": o,
        "sst": col(M[i], "sea_surface_temperature"), "wave": col(M[i], "wave_height"),
        "curVel": col(M[i], "ocean_current_velocity"), "curDir": col(M[i], "ocean_current_direction"),
        "windSpeedMs": col(W[i], "windspeed_10m"), "windDir": col(W[i], "winddirection_10m"),
    } for i, (a, o) in enumerate(pairs)]
    return {"times": times, "points": points, "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": ["Open-Meteo Marine API", "Open-Meteo Weather API"]}


def grid_data(d=None):
    return cached(f"grid:{d}", 1800, lambda: build_grid(d))


@app.get("/api/grid")
def grid(date: str | None = None):
    d = _parse_date(date)
    try:
        g = grid_data(d)
    except Exception as e:
        raise HTTPException(502, f"Open-Meteo unavailable: {e}")
    t = datetime.now(timezone.utc).date()
    return {**g, "date": d or t.isoformat(), "now_index": start_index(g["times"], d),
            "date_range": [(t - timedelta(days=60)).isoformat(), (t + timedelta(days=7)).isoformat()]}


def build_ocean(d):
    d = d or datetime.now(timezone.utc).date().isoformat()
    days = [(_date.fromisoformat(d) + timedelta(days=i)).isoformat() for i in range(3)]
    pairs = [(a, o) for a in LATS for o in LONS]
    sd, ed = _dates(d)

    def sea():
        def one(c):
            r = fetch_sealevel(",".join(str(p[0]) for p in c), ",".join(str(p[1]) for p in c), 3, sd, ed)
            return r if isinstance(r, list) else [r]
        with ThreadPoolExecutor(4) as ex:
            rs = [x for part in ex.map(one, [pairs[i:i + 40] for i in range(0, len(pairs), 40)]) for x in part]
        return [[_safe_float(v) for v in r["hourly"]["sea_level_height_msl"]] for r in rs]

    def cm(k):
        arr = fetch_layer(k, LATS, LONS, days)
        return [[arr[h // 24][r][c] for h in range(72)] for r in range(len(LATS)) for c in range(len(LONS))]

    jobs = {"sealevel": (sea, "Open-Meteo Marine (sea_level_height_msl)")}
    for k in SPECS:
        jobs[k] = ((lambda k=k: cm(k)), "Copernicus Marine " + SPECS[k][0])
    with ThreadPoolExecutor(6) as ex:
        futs = {k: ex.submit(f) for k, (f, _) in jobs.items()}
    cols, info = {}, {}
    for k, fu in futs.items():
        try:
            col = fu.result()
            vals = sorted(v for r in col for v in r if v is not None)
            cols[k] = col
            info[k] = {"available": bool(vals), "source": jobs[k][1], "note": NOTES.get(k),
                       "range": [vals[int(len(vals) * .02)], vals[max(0, int(len(vals) * .98) - 1)]] if vals else None,
                       "error": None if vals else "No data returned for this area/date"}
        except Exception as e:
            info[k] = {"available": False, "source": jobs[k][1], "range": None, "error": str(e)[:240]}
    return {"cols": cols, "layers": info, "date": d}


@app.get("/api/grid/ocean")
def grid_ocean(date: str | None = None):
    d = _parse_date(date)
    return cached(f"ocean:{d}", 10800, lambda: build_ocean(d))


@app.get("/api/point")
def point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    try:
        d = cached(f"pt{lat:.2f},{lon:.2f}", 900, lambda: fetch_combined_point(lat, lon, 3))
    except Exception as e:
        raise HTTPException(502, f"Open-Meteo unavailable: {e}")
    for h in d["hours"]:
        h["assessment"] = assess(h["wave_m"], h["wind_speed_kmh"])
    d["now_index"] = now_index([h["time"] for h in d["hours"]])
    return d


@app.get("/api/cities")
def cities():
    return [{"name": n.title(), "lat": c[0], "lon": c[1]} for n, c in CITIES.items()]


# ------------------------------------------------------------------ agents
_graph, _graph_err = None, None


def get_graph():
    global _graph, _graph_err
    if _graph is None and _graph_err is None:
        try:
            mm = ModelManager()
            _graph = build_graph(ORCAOrchestrator(mm), OceanAgent(mm), WeatherAgent(mm),
                                 GeospatialAgent(mm), MarineAnalyst(mm))
        except Exception as e:
            _graph_err = str(e)
    return _graph


@app.get("/api/health")
def health():
    g = get_graph()
    return {"status": "ok", "agents_online": g is not None, "agent_error": _graph_err}


SESS = {}
TOMORROW = ("tomorrow", "कल", "நாளை", "రేపు", "നാളെ", "আগামীকাল", "આવતીકાલે", "ನಾಳೆ")


class Ask(BaseModel):
    query: str
    lat: float | None = None
    lon: float | None = None
    session_id: str = "default"
    date: str | None = None


def _intent(q, times, prev=None, d=None):
    ql = q.lower()
    kinds = {"wave": ("wave", "swell", "sea state", "safe", "fish", "boat"),
             "wind": ("wind", "gust", "storm"), "current": ("current", "drift"),
             "temperature": ("temp", "sst", "warm", "cold")}
    layer = next((l for l, ks in kinds.items() if any(k in ql for k in ks)), prev)
    day = 2 if "day after" in ql else 1 if any(t in ql for t in TOMORROW) else 0
    now = start_index(times, d)
    return layer, (min(len(times) - 1, (now // 24 + day) * 24 + 6) if day else now)


def _series_alerts(g, lat, lon):
    n = len(g["times"])
    return {"time": g["times"], "wave": [idw(g, lat, lon, h, "wave") for h in range(n)],
            "wind_kmh": [(lambda w: None if w is None else w * 3.6)(idw(g, lat, lon, h, "windSpeedMs")) for h in range(n)],
            "current": [idw(g, lat, lon, h, "curVel") for h in range(n)]}


@app.get("/api/geofences")
def geofences():
    return GEOFENCES


@app.get("/api/geofence/check")
def gf_check(lat: float, lon: float):
    return geofence_check(lat, lon)


@app.get("/api/alerts")
def alerts(lat: float, lon: float):
    s = cached(f"al{lat:.2f},{lon:.2f}", 900, lambda: _series_alerts(grid_data(), lat, lon))
    return {"location": {"latitude": lat, "longitude": lon}, "alerts": scan_alerts(s)}


@app.get("/api/alerts/overview")
def overview():
    def build():
        g, out = grid_data(), []
        for n, c in CITIES.items():
            for a in scan_alerts(_series_alerts(g, c[0], c[1])):
                out.append({**a, "city": n.title(), "lat": c[0], "lon": c[1]})
        return sorted(out, key=lambda a: (a["level"] != "high", a["index"]))
    try:
        return {"alerts": cached("overview", 900, build), "disclaimer": "Forecast-derived, not an official IMD warning."}
    except Exception as e:
        raise HTTPException(502, f"Open-Meteo unavailable: {e}")


def _extras(d, lat, lon, i):
    """Salinity/sea level/chl/pH/O2/biomass at the asked place, from the cached ocean grid."""
    oc, g = _cache.get(f"ocean:{d}"), _cache.get(f"grid:{d}")
    if not oc or not g:
        return {}
    meta = {"salinity": ("Salinity", "PSU", 2), "sealevel": ("Sea level", "m", 2), "chlorophyll": ("Chlorophyll-a", "mg/m³", 2),
            "ph": ("pH", "", 2), "oxygen": ("Oxygen", "mmol/m³", 0), "biomass": ("Phyto. biomass", "mmol/m³", 2)}
    out = {}
    for k, (lb, u, dg) in meta.items():
        col = oc[1]["cols"].get(k)
        if not col:
            continue
        gg = {"points": [{"lat": p["lat"], "lon": p["lon"], "v": col[n]} for n, p in enumerate(g[1]["points"])]}
        ser = [idw(gg, lat, lon, h, "v") for h in range(len(g[1]["times"]))]
        if i < len(ser) and ser[i] is not None:
            out[k] = {"label": lb, "unit": u, "d": dg, "value": ser[i], "series": ser}
    return out


@app.post("/api/ask")
def ask(body: Ask):
    q = body.query.strip()
    if not q:
        raise HTTPException(400, "Empty query")
    d = _parse_date(body.date)
    sd, ed = _dates(d)
    S = SESS.setdefault(body.session_id, {"loc": None, "layer": None, "turns": []})
    lang, nq = detect_lang(q), normalize(q)
    city, lat, lon = resolve_location(nq)
    if city == "Default location":
        if body.lat is not None and body.lon is not None:
            city, lat, lon = "Selected point", body.lat, body.lon
        elif S["loc"]:
            city, lat, lon = S["loc"]
    route, names = None, find_cities(nq, CITIES)
    if len(names) >= 2 and any(w in nq.lower() for w in ("route", "path", "navigate", "sail", "way")):
        try:
            g = grid_data(d)
            route = plan_route(g, CITIES[names[0]], CITIES[names[1]], start_index(g["times"], d), assess)
            city, (lat, lon) = names[0].title(), CITIES[names[0]]
        except Exception as e:
            route = None
    S["loc"] = (city, lat, lon)

    ctx = " | ".join(S["turns"][-3:])
    llm_q = nq + (f"\n[Earlier in this conversation: {ctx}]" if ctx else "") \
        + (f"\n[Reply in {lang}.]" if lang != "English" else "")
    if route:
        llm_q += (f"\n[ORCA route engine ({names[0]} to {names[1]}): {route['distance_km']} km, max risk "
                  f"{route['max_risk']}/100, mean {route['mean_risk']}/100. {route['notes']}]")
    S["turns"].append(q)

    answer, llm_ok, note, plan, s = None, False, None, [], {}
    g_ = get_graph()
    if g_:
        try:
            st = g_.invoke({"user_query": llm_q, "location_name": city, "latitude": lat, "longitude": lon,
                            "timestamp": None, "start_date": sd, "end_date": ed, "subtasks": [], "ocean_data": {}, "weather_data": {},
                            "geospatial_data": {}, "marine_analysis": {}, "recommendations": {},
                            "final_answer": ""})
            o, w = st["ocean_data"], st["weather_data"]
            s = {"time": o["time"], "sst": o["sst_c"], "wave": o["wave_height_m"],
                 "current": o["current_velocity_ms"], "current_dir": o["current_direction_deg"],
                 "wind_kmh": w["wind_speed_kmh"], "wind_dir": w["wind_direction_deg"]}
            answer, llm_ok = st["final_answer"], True
            m = re.search(r"\{.*\}", (st["subtasks"] or [""])[0], re.S)
            plan = json.loads(m.group(0)).get("agents", []) if m else []
        except Exception as e:
            note = f"LLM pipeline failed: {e}"
    else:
        note = f"LLM agents offline: {_graph_err}"

    if not s:
        try:
            hrs = fetch_combined_point(lat, lon, 3, sd, ed)["hours"]
        except Exception as e:
            raise HTTPException(502, f"Open-Meteo unavailable: {e}")
        s = {"time": [h["time"] for h in hrs], "sst": [h["sst_c"] for h in hrs],
             "wave": [h["wave_m"] for h in hrs], "current": [h["current_velocity_ms"] for h in hrs],
             "current_dir": [h["current_direction_deg"] for h in hrs],
             "wind_kmh": [h["wind_speed_kmh"] for h in hrs], "wind_dir": [h["wind_direction_deg"] for h in hrs]}

    layer, i = _intent(nq, s["time"], S["layer"], d)
    S["layer"] = layer
    v = {"sst_c": s["sst"][i], "wave_m": s["wave"][i], "wind_kmh": s["wind_kmh"][i],
         "wind_dir": s["wind_dir"][i], "current_ms": s["current"][i], "current_dir": s["current_dir"][i]}
    a = assess(v["wave_m"], v["wind_kmh"])
    if not answer:
        f = lambda x, d=1: "n/a" if x is None else f"{x:.{d}f}"
        answer = (f"**{city}** at {s['time'][i]} UTC (rule-based summary, no LLM):\n"
                  f"- Sea temperature {f(v['sst_c'])} °C, waves {f(v['wave_m'])} m, "
                  f"wind {f(v['wind_kmh'], 0)} km/h, current {f(v['current_ms'], 2)} m/s\n"
                  f"- Verdict: **{a['label']}**. PFZ / chlorophyll data is not connected, so no fishing-zone advice.")
        if route:
            answer += f"\n- Route {names[0].title()} → {names[1].title()}: {route['distance_km']} km, max risk {route['max_risk']}/100."
    on, skip = "done", "skipped"
    return {
        "query": q, "location": {"name": city, "latitude": lat, "longitude": lon},
        "language": lang, "turn": len(S["turns"]),
        "ui": {"layer": layer, "hour_index": i, "zoom": 5.5 if route else 6.5},
        "time": s["time"][i], "values": v, "assessment": a,
        "date": d, "extra": _extras(d, lat, lon, i), "alerts": scan_alerts(s), "geofence": geofence_check(lat, lon), "route": route,
        "series": {"time": s["time"], "sst": s["sst"], "wave": s["wave"],
                   "wind_kmh": s["wind_kmh"], "current": s["current"]},
        "answer": answer, "llm_ok": llm_ok, "note": note, "plan": plan,
        "agents": [{"name": "Orchestrator", "status": on if llm_ok else skip},
                   {"name": "Ocean", "status": on}, {"name": "Weather", "status": on},
                   {"name": "Geofence/Route", "status": on}, {"name": "Analyst", "status": on if llm_ok else skip}],
        "unavailable": ["PFZ advisory", "Chlorophyll-a", "Tides", "Official cyclone / lightning alerts",
                        "Legal maritime boundaries (demo zones only)"],
    }


STATIC = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
