from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.core.database import db
from app.core.security import public_many
from app.dependencies.auth import require_roles
from app.services.certificate_service import verify_certificate

router = APIRouter(tags=["certificates"])


@router.get("/certificates/verify/{cert_id}")
async def public_verify_json(cert_id: str, request: Request) -> Dict[str, Any]:
    """Public certificate verification endpoint (JSON). No authentication required."""
    return await verify_certificate(cert_id, request)


@router.get("/certificates/verify/{cert_id}/view", response_class=HTMLResponse)
async def public_verify_html(cert_id: str, request: Request) -> str:
    """Public certificate verification page (HTML). Shows official validation status card."""
    result = await verify_certificate(cert_id, request)
    valid = result.get("valid")
    status = result.get("status", "invalid")
    color = "#0EA5A0" if valid else ("#F59E0B" if status == "pending_approval" else "#EF4444")
    label = "VALID" if valid else ("PENDING" if status == "pending_approval" else "INVALID")

    body_rows = ""
    fields = [
        ("student_name", "Student"),
        ("course_title", "Course"),
        ("institute_name", "Institute"),
        ("issue_date", "Issue date"),
        ("completion_date", "Completion date"),
        ("certificate_id", "Certificate ID"),
    ]
    for k, label_k in fields:
        v = result.get(k) or "—"
        if isinstance(v, str) and "T" in v:
            v = v[:10]
        body_rows += f"<tr><td style='padding:10px 12px;color:#64748B;font-size:12px;letter-spacing:.5px'>{label_k}</td><td style='padding:10px 12px;color:#0F1E33;font-size:14px;font-weight:600'>{v}</td></tr>"

    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Verify · {cert_id}</title><style>body{{font-family:-apple-system,system-ui,sans-serif;background:#F7F9FC;color:#0F1E33;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px}}.card{{max-width:520px;width:100%;background:#fff;border-radius:20px;box-shadow:0 20px 40px rgba(15,30,51,.08);padding:32px;border:1px solid #E2E8F0}}.badge{{display:inline-block;padding:8px 16px;border-radius:999px;font-size:12px;font-weight:800;letter-spacing:1.5px;color:#fff;background:{color}}}h1{{font-size:22px;color:#1E3A5F;margin:16px 0 4px}}p{{color:#64748B;font-size:14px;margin:0}}table{{width:100%;margin-top:20px;border-collapse:collapse}}tr{{border-bottom:1px solid #F1F5F9}}tr:last-child{{border-bottom:0}}.foot{{margin-top:20px;font-size:12px;color:#64748B}}</style></head><body><div class=card><div class=badge>{label}</div><h1>CORZAAR Certificate Verification</h1><p>{'This certificate is authentic and issued by CORZAAR.' if valid else 'This certificate could not be verified.'}</p><table>{body_rows}</table><p class=foot>Verified via CORZAAR · corzaar.app</p></div></body></html>"""


@router.get("/me/certificates")
async def my_certificates(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    """Retrieve all certificates earned by the authenticated student."""
    return public_many(await db.certificates.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100))
