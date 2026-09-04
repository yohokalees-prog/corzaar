from typing import List, Optional
from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    mobile: str = Field(min_length=8, max_length=15)
    role: str = "student"


class OtpVerify(BaseModel):
    mobile: str
    otp: str
    role: str = "student"
    full_name: Optional[str] = None


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminVerify(BaseModel):
    email: str
    otp: str


class ProfileUpdate(BaseModel):
    full_name: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    academic_qualifications: Optional[str] = None
    preferred_courses: List[str] = []
    language: str = "English"
