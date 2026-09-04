from typing import List, Optional
from pydantic import BaseModel


class MerchantRegistration(BaseModel):
    institute_name: str
    address: str
    contact_person: str
    mobile: str
    email: Optional[str] = None
    institute_details: str = ""
    bank_details: str
    documents: List[str] = []


class PayoutRecord(BaseModel):
    merchant_id: str
    amount: float
    method: str = "bank_transfer"
    reference: str = ""
    notes: str = ""
