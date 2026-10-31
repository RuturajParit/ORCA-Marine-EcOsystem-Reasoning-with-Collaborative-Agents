from core.model_manager import ModelManager
from core.orchestrator import ORCAOrchestrator
from core.graph import build_graph

from agents.ocean_agent import OceanAgent
from agents.weather_agent import WeatherAgent
from agents.geospatial_agent import GeospatialAgent
from agents.analyst_agent import MarineAnalyst


CITIES = {
    "mumbai": (18.90, 72.70),
    "goa": (15.45, 73.55),
    "mangalore": (12.80, 74.70),
    "kochi": (9.85, 76.05),
    "chennai": (13.05, 80.35),
    "visakhapatnam": (17.70, 83.35),
    "kolkata": (21.55, 88.20),
    "porbandar": (21.60, 69.45),
}


def resolve_location(query: str):
    q = query.lower()

    for city, coords in CITIES.items():
        if city in q:
            return city.title(), coords[0], coords[1]

    # Optional syntax: "lat 18.90 lon 72.70"
    import re
    match = re.search(
        r"lat(?:itude)?\s*(-?\d+(?:\.\d+)?)\s+lon(?:gitude)?\s*(-?\d+(?:\.\d+)?)",
        q
    )
    if match:
        return "Custom location", float(match.group(1)), float(match.group(2))

    return "Default location", 15.49, 73.83


def main():
    print("=" * 72)
    print("                 ORCA MARINE")
    print(" Marine EcOsystem Reasoning with Collaborative Agents")
    print("=" * 72)

    model_manager = ModelManager()

    print(f"\nNVIDIA NIM APIs: {len(model_manager.models)}")
    for model in model_manager.models:
        print(f"  ✓ {model.name}: {model.model}")

    orchestrator = ORCAOrchestrator(model_manager)
    ocean = OceanAgent(model_manager)
    weather = WeatherAgent(model_manager)
    geospatial = GeospatialAgent(model_manager)
    analyst = MarineAnalyst(model_manager)

    graph = build_graph(
        orchestrator,
        ocean,
        weather,
        geospatial,
        analyst
    )

    query = input("\nAsk ORCA > ").strip()
    if not query:
        print("Please enter a query.")
        return

    city, lat, lon = resolve_location(query)

    print(f"\n[LOCATION] {city}: {lat:.4f}, {lon:.4f}")
    print("[DATA] Open-Meteo Marine + Weather APIs")

    initial_state = {
        "user_query": query,
        "location_name": city,
        "latitude": lat,
        "longitude": lon,
        "timestamp": None,

        "subtasks": [],

        "ocean_data": {},
        "weather_data": {},
        "geospatial_data": {},

        "marine_analysis": {},
        "recommendations": {},
        "final_answer": ""
    }

    try:
        result = graph.invoke(initial_state)

        print("\n" + "=" * 72)
        print("                         ORCA RESULT")
        print("=" * 72)
        print(result["final_answer"])

    except Exception as exc:
        print("\n" + "=" * 72)
        print("                         ORCA ERROR")
        print("=" * 72)
        print(exc)


if __name__ == "__main__":
    main()
