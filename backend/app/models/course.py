from typing import List, Optional
from pydantic import BaseModel


class CourseCreate(BaseModel):
    title: str
    description: str
    category: str
    fees: float = 0
    duration: str = "8 weeks"
    curriculum: List[str] = []
    institute_id: Optional[str] = None
