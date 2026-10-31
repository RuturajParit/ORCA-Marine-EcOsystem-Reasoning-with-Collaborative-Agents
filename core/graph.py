from langgraph.graph import StateGraph, START, END
from core.state import ORCAState


def build_graph(orchestrator, ocean, weather, geospatial, analyst):
    graph = StateGraph(ORCAState)

    graph.add_node("orchestrator", orchestrator.plan)
    graph.add_node("ocean", ocean.run)
    graph.add_node("weather", weather.run)
    graph.add_node("geospatial", geospatial.run)
    graph.add_node("analyst", analyst.run)

    graph.add_edge(START, "orchestrator")

    # Specialist agents execute in parallel.
    graph.add_edge("orchestrator", "ocean")
    graph.add_edge("orchestrator", "weather")
    graph.add_edge("orchestrator", "geospatial")

    # Analyst receives the merged state after all three finish.
    graph.add_edge("ocean", "analyst")
    graph.add_edge("weather", "analyst")
    graph.add_edge("geospatial", "analyst")

    graph.add_edge("analyst", END)

    return graph.compile()
