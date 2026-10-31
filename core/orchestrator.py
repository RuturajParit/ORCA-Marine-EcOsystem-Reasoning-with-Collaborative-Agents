from core.state import ORCAState


class ORCAOrchestrator:
    def __init__(self, model_manager):
        self.llm = model_manager

    def plan(self, state: ORCAState):
        query = state["user_query"]

        prompt = f"""
You are ORCA, the central coordinator for a marine
intelligence and decision-support system.

User query:
{query}

Location:
{state["location_name"]} ({state["latitude"]}, {state["longitude"]})

Available specialist agents:
1. ocean:
   SST, chlorophyll, waves, currents, tides
2. weather:
   forecast, wind, cyclone, lightning, marine alerts
3. geospatial:
   route, maritime boundaries, geofencing, restricted zones

Choose the required agents.

Return ONLY JSON:
{{"agents":["ocean","weather","geospatial"]}}
"""
        print("\n[ORCA PLAN] Sending request to NVIDIA NIM...",
        flush=True
        )
        result = self.llm.call(
            [
                {
                    "role": "system",
                    "content": "You coordinate ORCA marine specialist agents."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=4096
        )

        print("\n[ORCA PLAN]")
        print(result)

        # IMPORTANT:
        # Return only fields owned by this node.
        return {
            "subtasks": [result]
        }
