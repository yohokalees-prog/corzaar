from typing import List, Optional
from pydantic import BaseModel


class CartChange(BaseModel):
    course_id: str


class EnrollmentCreate(BaseModel):
    course_id: str
    batch_id: Optional[str] = None
    coupon_code: Optional[str] = None
    referral_code: Optional[str] = None
    use_wallet: bool = False


class CheckoutCreate(BaseModel):
    enrollment_id: str


class ProgressUpdate(BaseModel):
    completed: List[str]
