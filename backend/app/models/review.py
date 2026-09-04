from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = ""
    target_type: str  # "courses" or "institutes"
    target_id: str


class RefundRequest(BaseModel):
    enrollment_id: str
    reason: str
