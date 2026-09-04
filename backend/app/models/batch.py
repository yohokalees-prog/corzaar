from typing import Optional
from pydantic import BaseModel


class BatchCreate(BaseModel):
    course_id: str
    schedule: str
    capacity: int = 30
    coordinator: str
    start_date: str
    end_date: str
    meet_link: Optional[str] = None


class AttendanceMark(BaseModel):
    student_id: str
    present: bool = True
    date: Optional[str] = None


class SessionCreate(BaseModel):
    date: str
    topic: Optional[str] = None


class SessionAttendance(BaseModel):
    student_id: str
    present: bool = True
