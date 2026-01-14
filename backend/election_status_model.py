from pydantic import BaseModel

class ElectionStatusUpdate(BaseModel):
    status: str  # "Active", "Paused", "Ended", "Upcoming"
