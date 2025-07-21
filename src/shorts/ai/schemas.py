from pydantic import BaseModel
from typing import List

class Moment(BaseModel):
    timestamp: str
    highlight: str
    b_roll_suggestion: str
    keywords: List[str]

class AllMoments(BaseModel):
    moments: List[Moment]