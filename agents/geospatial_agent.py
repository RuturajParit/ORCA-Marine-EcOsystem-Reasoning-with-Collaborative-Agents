from core.state import ORCAState


class GeospatialAgent:
    def __init__(self, model_manager):
        self.llm = model_manager

    def run(self, state: ORCAState):
        print("[GEOSPATIAL & ROUTE AGENT]")

        # This agent currently receives the same location context
        # and prepares the structure for PostGIS / boundaries / routing.
        # It does not invent geospatial results.
        geospatial_data = {
            "origin": {
                "name": state["location_name"],
                "latitude": state["latitude"],
                "longitude": state["longitude"]
            },

            "distance_to_boundary": None,
            "restricted_area": None,
            "marine_zone": None,
            "recommended_route": None,
            "route_risk": None,

            "source_status": (
                "PostGIS / maritime boundary adapter not connected yet"
            )
        }

        return {
            "geospatial_data": geospatial_data
        }
