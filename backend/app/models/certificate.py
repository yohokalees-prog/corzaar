from typing import Optional
from pydantic import BaseModel, Field


class CertTemplateCreate(BaseModel):
    name: str
    style: str = "classic"  # classic | modern | bold
    accent_color: str = "#1E3A5F"
    signatory: str = ""
    image_base64: Optional[str] = None  # optional custom background PNG/JPG data URI


class CertConfigUpdate(BaseModel):
    enabled: bool = True
    template_id: Optional[str] = None
    certificate_name: Optional[str] = None
    completion_percent: int = Field(default=100, ge=10, le=100)
    issue_method: str = "automatic"  # automatic | manual
