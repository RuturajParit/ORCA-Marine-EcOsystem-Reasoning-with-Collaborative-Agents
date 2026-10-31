from core.state import ORCAState
from data.open_meteo import fetch_weather, _safe_float


class WeatherAgent:
    def __init__(self, model_manager):
        self.llm = model_manager

    def run(self, state: ORCAState):
        print("[WEATHER & SAFETY AGENT] Fetching Open-Meteo Weather data...")

        weather = fetch_weather(
            state["latitude"],
            state["longitude"],
            forecast_days=3,
            start_date=state.get("start_date"),
            end_date=state.get("end_date")
        )

        hourly = weather.get("hourly", {})

        wind_ms = [
            _safe_float(x)
            for x in hourly.get("windspeed_10m", [])
        ]

        wind_kmh = [
            x * 3.6 if x is not None else None
            for x in wind_ms
        ]

        weather_data = {
            "location": {
                "name": state["location_name"],
                "latitude": state["latitude"],
                "longitude": state["longitude"]
            },

            "provider": "Open-Meteo Weather API",

            "time": hourly.get("time", []),

            "wind_speed_ms": wind_ms,
            "wind_speed_kmh": wind_kmh,

            "wind_direction_deg": [
                _safe_float(x)
                for x in hourly.get(
                    "winddirection_10m", []
                )
            ],

            # Not supplied by the exact HTML weather endpoint.
            "forecast": None,
            "cyclone": None,
            "lightning": None,
            "marine_alerts": [],

            "source_url": (
                "https://api.open-meteo.com/v1/forecast"
            )
        }

        if weather_data["time"]:
            weather_data["current_snapshot"] = {
                "time": weather_data["time"][0],
                "wind_speed_ms": (
                    weather_data["wind_speed_ms"][0]
                    if weather_data["wind_speed_ms"] else None
                ),
                "wind_speed_kmh": (
                    weather_data["wind_speed_kmh"][0]
                    if weather_data["wind_speed_kmh"] else None
                ),
                "wind_direction_deg": (
                    weather_data["wind_direction_deg"][0]
                    if weather_data["wind_direction_deg"] else None
                )
            }
        else:
            weather_data["current_snapshot"] = {}

        return {
            "weather_data": weather_data
        }
