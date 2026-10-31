from typing import TypedDict, Optional, List, Dict


class ORCAState(TypedDict):
    user_query: str
    location_name: str
    latitude: float
    longitude: float
    timestamp: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]

    subtasks: List[str]

    ocean_data: Dict
    weather_data: Dict
    geospatial_data: Dict

    marine_analysis: Dict
    recommendations: Dict
    final_answer: str
