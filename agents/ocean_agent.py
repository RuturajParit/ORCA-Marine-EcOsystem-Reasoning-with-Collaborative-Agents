from core.state import ORCAState
from data.open_meteo import fetch_marine, _safe_float


class OceanAgent:
    def __init__(self, model_manager):
        self.llm = model_manager

    def run(self, state: ORCAState):
        print("[OCEAN & DATA AGENT] Fetching Open-Meteo Marine data...")

        marine = fetch_marine(
            state["latitude"],
            state["longitude"],
            forecast_days=3,
            start_date=state.get("start_date"),
            end_date=state.get("end_date")
        )

        hourly = marine.get("hourly", {})

        ocean_data = {
            "location": {
                "name": state["location_name"],
                "latitude": state["latitude"],
                "longitude": state["longitude"]
            },

            "provider": "Open-Meteo Marine API",

            "time": hourly.get("time", []),

            "sst_c": [
                _safe_float(x)
                for x in hourly.get(
                    "sea_surface_temperature", []
                )
            ],

            "wave_height_m": [
                _safe_float(x)
                for x in hourly.get(
                    "wave_height", []
                )
            ],

            "current_velocity_ms": [
                _safe_float(x)
                for x in hourly.get(
                    "ocean_current_velocity", []
                )
            ],

            "current_direction_deg": [
                _safe_float(x)
                for x in hourly.get(
                    "ocean_current_direction", []
                )
            ],

            # These are intentionally unavailable from this endpoint.
            "chlorophyll_a": None,
            "tides": None,

            "source_url": (
                "https://marine-api.open-meteo.com/v1/marine"
            )
        }

        # Convenient current/first-hour values for downstream agents.
        if ocean_data["time"]:
            ocean_data["current_snapshot"] = {
                "time": ocean_data["time"][0],
                "sst_c": ocean_data["sst_c"][0] if ocean_data["sst_c"] else None,
                "wave_height_m": ocean_data["wave_height_m"][0] if ocean_data["wave_height_m"] else None,
                "current_velocity_ms": (
                    ocean_data["current_velocity_ms"][0]
                    if ocean_data["current_velocity_ms"] else None
                ),
                "current_direction_deg": (
                    ocean_data["current_direction_deg"][0]
                    if ocean_data["current_direction_deg"] else None
                )
            }
        else:
            ocean_data["current_snapshot"] = {}

        return {
            "ocean_data": ocean_data
        }
