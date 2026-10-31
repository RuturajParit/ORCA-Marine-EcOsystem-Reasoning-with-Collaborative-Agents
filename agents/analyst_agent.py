from core.state import ORCAState


def _min_valid(values):
    vals = [v for v in values if v is not None]
    return min(vals) if vals else None


def _max_valid(values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


class MarineAnalyst:
    def __init__(self, model_manager):
        self.llm = model_manager

    def run(self, state: ORCAState):
        print("[MARINE ANALYSIS AGENT] Combining specialist data...")

        ocean = state["ocean_data"]
        weather = state["weather_data"]
        geo = state["geospatial_data"]

        waves = ocean.get("wave_height_m", [])
        winds = weather.get("wind_speed_kmh", [])
        sst = ocean.get("sst_c", [])

        analysis = {
            "data_sources": [
                "Open-Meteo Marine API",
                "Open-Meteo Weather API"
            ],

            "location": {
                "name": state["location_name"],
                "latitude": state["latitude"],
                "longitude": state["longitude"]
            },

            "ocean_summary": {
                "sst_min_c": _min_valid(sst),
                "sst_max_c": _max_valid(sst),
                "wave_min_m": _min_valid(waves),
                "wave_max_m": _max_valid(waves),
            },

            "weather_summary": {
                "wind_min_kmh": _min_valid(winds),
                "wind_max_kmh": _max_valid(winds),
            },

            "pfz": {
                "status": "not_available",
                "reason": (
                    "The connected Open-Meteo endpoint does not provide "
                    "chlorophyll/PFZ advisory data."
                )
            },

            "geospatial": geo
        }

        prompt = f"""
You are ORCA's final Marine Analysis Agent.

User query:
{state["user_query"]}

Location:
{state["location_name"]}
Latitude: {state["latitude"]}
Longitude: {state["longitude"]}

REAL OCEAN DATA FETCHED FROM OPEN-METEO:
{ocean}

REAL WEATHER DATA FETCHED FROM OPEN-METEO:
{weather}

GEOSPATIAL DATA:
{geo}

Give an explainable marine decision-support answer.

Rules:
- Use only values present in the supplied data.
- Do NOT invent chlorophyll, PFZ locations, tides, cyclone alerts,
  restricted zones, maritime boundaries, or route results.
- Open-Meteo data is forecast data, not an official fishing advisory.
- For "best fishing area" questions, explain that a genuine PFZ
  recommendation requires validated PFZ/chlorophyll/ocean-colour data.
- You may assess wave/wind conditions from the supplied values.
- Clearly separate what is known from what is unavailable.

Structure:
1. Location
2. Ocean conditions
3. Wind/safety conditions
4. Fishing/PFZ assessment
5. Navigation/geospatial assessment
6. Recommendation
"""

        llm_result = self.llm.call(
            [
                {
                    "role": "system",
                    "content": (
                        "You are ORCA, a marine decision-support "
                        "analysis agent. Be factual and conservative."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2500
        )

        analysis["llm_explanation"] = llm_result

        return {
            "marine_analysis": analysis,
            "final_answer": llm_result
        }
