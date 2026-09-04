from typing import Optional
from pydantic import BaseModel, Field


class CouponCreate(BaseModel):
    code: str
    description: str = ""
    discount_percent: int = Field(ge=1, le=100)
    course_id: Optional[str] = None  # None => applies to all merchant courses


class CouponValidate(BaseModel):
    code: str
    course_id: str
