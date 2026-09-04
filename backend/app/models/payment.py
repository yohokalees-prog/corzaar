from pydantic import BaseModel


class CashoutRequest(BaseModel):
    upi_id: str
    amount: float


class CashoutAction(BaseModel):
    reference: str = ""
