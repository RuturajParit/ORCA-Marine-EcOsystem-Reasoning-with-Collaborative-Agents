"""
Open-Meteo adapters based directly on the working HTML prototype.

Marine endpoint:
https://marine-api.open-meteo.com/v1/marine

Weather endpoint:
https://api.open-meteo.com/v1/forecast

Marine variables used by the HTML:
- wave_height
- sea_surface_temperature
- ocean_current_velocity
- ocean_current_direction

Weather variables used by the HTML:
- windspeed_10m
- winddirection_10m

No API key is required by Open-Meteo for the normal public endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import requests


MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

TIMEOUT = (15, 60)


def _get_json(url: str, params: Dict[str, Any]) -> Any:
    response = requests.get(
        url,
        params=params,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def _range(params, start_date, end_date):
    """Use an explicit date window (UTC days) instead of forecast_days."""
    if start_date:
        params.pop("forecast_days", None)
        params["start_date"], params["end_date"] = start_date, end_date or start_date


def fetch_sealevel(latitude, longitude, forecast_days=3, start_date=None, end_date=None):
    """Sea level incl. tides (m vs mean sea level) from Open-Meteo Marine."""
    params = {"latitude": latitude, "longitude": longitude, "hourly": "sea_level_height_msl",
              "timezone": "UTC", "forecast_days": forecast_days}
    _range(params, start_date, end_date)
    return _get_json(MARINE_URL, params)


def fetch_marine(
    latitude: float,
    longitude: float,
    forecast_days: int = 3,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": (
            "wave_height,"
            "sea_surface_temperature,"
            "ocean_current_velocity,"
            "ocean_current_direction"
        ),
        "timezone": "UTC",
        "forecast_days": forecast_days
    }

    _range(params, start_date, end_date)
    return _get_json(MARINE_URL, params)


def fetch_weather(
    latitude: float,
    longitude: float,
    forecast_days: int = 3,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "windspeed_10m,winddirection_10m",
        "windspeed_unit": "ms",
        "timezone": "UTC",
        "forecast_days": forecast_days
    }

    _range(params, start_date, end_date)
    return _get_json(WEATHER_URL, params)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def combine_point_forecast(
    marine: Dict[str, Any],
    weather: Dict[str, Any]
) -> Dict[str, Any]:

    mh = marine.get("hourly", {})
    wh = weather.get("hourly", {})

    times = mh.get("time") or wh.get("time") or []

    result = []

    for i, time_value in enumerate(times):
        wind_ms = _safe_float(
            (wh.get("windspeed_10m") or [None] * len(times))[i]
            if i < len(wh.get("windspeed_10m", []))
            else None
        )

        wind_kmh = (
            wind_ms * 3.6
            if wind_ms is not None
            else None
        )

        result.append({
            "time": time_value,

            "sst_c": _safe_float(
                mh.get("sea_surface_temperature", [None] * len(times))[i]
            ) if i < len(mh.get("sea_surface_temperature", [])) else None,

            "wave_m": _safe_float(
                mh.get("wave_height", [None] * len(times))[i]
            ) if i < len(mh.get("wave_height", [])) else None,

            "current_velocity_ms": _safe_float(
                mh.get("ocean_current_velocity", [None] * len(times))[i]
            ) if i < len(mh.get("ocean_current_velocity", [])) else None,

            "current_direction_deg": _safe_float(
                mh.get("ocean_current_direction", [None] * len(times))[i]
            ) if i < len(mh.get("ocean_current_direction", [])) else None,

            "wind_speed_ms": wind_ms,
            "wind_speed_kmh": wind_kmh,

            "wind_direction_deg": _safe_float(
                wh.get("winddirection_10m", [None] * len(times))[i]
            ) if i < len(wh.get("winddirection_10m", [])) else None,
        })

    return {
        "latitude": marine.get("latitude"),
        "longitude": marine.get("longitude"),
        "timezone": marine.get("timezone"),
        "elevation": marine.get("elevation"),
        "hours": result,
        "source": {
            "marine": MARINE_URL,
            "weather": WEATHER_URL
        }
    }


def fetch_combined_point(
    latitude: float,
    longitude: float,
    forecast_days: int = 3,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:

    marine = fetch_marine(
        latitude,
        longitude,
        forecast_days, start_date, end_date
    )

    weather = fetch_weather(
        latitude,
        longitude,
        forecast_days, start_date, end_date
    )

    return combine_point_forecast(
        marine,
        weather
    )


def nearest_hour_index(
    hours: list[dict[str, Any]],
    target: Optional[datetime] = None
) -> int:

    if not hours:
        return 0

    if target is None:
        # The first returned forecast hour is a safe default.
        return 0

    best_index = 0
    best_delta = None

    for i, item in enumerate(hours):
        try:
            dt = datetime.fromisoformat(
                item["time"].replace("Z", "+00:00")
            )
            delta = abs((dt - target).total_seconds())

            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_index = i

        except (KeyError, ValueError):
            continue

    return best_index
