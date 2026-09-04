import io
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import Request
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.core.database import db
from app.core.security import now


def gen_cert_id(institute_id: str, course_id: str) -> str:
    """Generate standardized certificate ID: CZ-CERT-[HEX8]."""
    return f"CZ-CERT-{secrets.token_hex(4).upper()}"


def verify_base_url(request: Optional[Request] = None) -> str:
    """Determine the public base URL for verification links."""
    origin = ""
    if request is not None:
        origin = str(request.base_url).rstrip("/")
    if not origin:
        origin = (settings.APP_PAYMENT_RETURN_URL or "https://corzaar.app").split("/api/")[0].rstrip("/")
    return origin


async def load_template(template_id: Optional[str]) -> Dict[str, Any]:
    """Retrieve template or default styles."""
    if not template_id:
        return {"style": "classic", "accent_color": "#1E3A5F", "signatory": ""}
    tpl = await db.certificate_templates.find_one({"id": template_id}, {"_id": 0})
    return tpl or {"style": "classic", "accent_color": "#1E3A5F", "signatory": ""}


def cert_html(
    name: str,
    course_title: str,
    institute_name: str,
    cert_id: str,
    issued_at: str,
    style: str = "classic",
    accent: str = "#1E3A5F",
    signatory: str = "",
    verify_url: str = "",
    status: str = "issued",
) -> str:
    """Render responsive, printable HTML certificate card."""
    status_banner = ""
    if status == "revoked":
        status_banner = "<div style='background:#EF4444;color:#fff;padding:8px 12px;border-radius:10px;font-size:12px;font-weight:800;letter-spacing:1px;margin:12px auto;display:inline-block'>REVOKED</div>"
    elif status == "pending_approval":
        status_banner = "<div style='background:#F59E0B;color:#fff;padding:8px 12px;border-radius:10px;font-size:12px;font-weight:800;letter-spacing:1px;margin:12px auto;display:inline-block'>PENDING APPROVAL</div>"

    bg = "#F7F9FC" if style != "bold" else "#0F1E33"
    card_bg = "#FFFFFF" if style != "bold" else "#1E3A5F"
    text_ink = "#0F1E33" if style != "bold" else "#FFFFFF"
    text_muted = "#64748B" if style != "bold" else "#DFF5EB"
    font_family = "'Georgia',serif" if style == "classic" else "-apple-system,system-ui,'Helvetica Neue',sans-serif"
    qr_html = ""
    if verify_url:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={verify_url}"
        qr_html = f"<div style='position:absolute;left:56px;bottom:56px;text-align:left'><img src='{qr_url}' width='96' height='96' alt='Verify QR' style='border-radius:8px;background:#fff;padding:4px'/><div style='font-size:9px;color:{text_muted};margin-top:6px;letter-spacing:.5px;font-family:-apple-system,sans-serif'>Scan to verify</div></div>"
    signatory_row = f"<div style='margin-top:24px;color:{text_muted};font-size:11px;letter-spacing:1px;text-transform:uppercase'>Authorised · {signatory}</div>" if signatory else ""

    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>CORZAAR Certificate · {name}</title><style>
    :root{{color-scheme:light}}body{{font-family:{font_family};background:{bg};color:{text_ink};margin:0;padding:24px;display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .cert{{background:{card_bg};max-width:820px;width:100%;padding:56px 48px;border-radius:20px;border:1px solid {accent}33;box-shadow:0 30px 60px rgba(15,30,51,.08);text-align:center;position:relative;overflow:hidden}}
    .cert::before{{content:'';position:absolute;inset:16px;border:2px solid {accent};border-radius:14px;pointer-events:none;opacity:.5}}
    .brand{{font-family:-apple-system,system-ui,sans-serif;letter-spacing:6px;font-size:12px;color:{accent};text-transform:uppercase;font-weight:800}}
    h1{{font-size:44px;color:{accent};margin:24px 0 8px;letter-spacing:-.5px}}
    .lead{{color:{text_muted};font-family:-apple-system,system-ui,sans-serif;font-size:14px}}
    h2{{font-size:34px;color:{text_ink};margin:28px 0 6px;font-weight:700}}
    .course{{font-size:20px;color:{accent};margin-top:8px;font-weight:700}}
    .meta{{margin-top:26px;color:{text_muted};font-family:-apple-system,system-ui,sans-serif;font-size:12px;letter-spacing:1px;text-transform:uppercase}}
    .row{{display:flex;justify-content:space-between;margin-top:44px;font-family:-apple-system,system-ui,sans-serif;gap:12px;flex-wrap:wrap}}
    .row div{{text-align:center;font-size:12px;color:{text_muted};min-width:120px}}
    .row strong{{display:block;color:{text_ink};font-size:14px;margin-bottom:6px;letter-spacing:.5px}}
    .seal{{position:absolute;right:56px;bottom:56px;width:80px;height:80px;border-radius:50%;background:#0EA5A0;color:#fff;display:flex;align-items:center;justify-content:center;font-family:-apple-system,system-ui,sans-serif;font-size:11px;font-weight:800;letter-spacing:1px;text-align:center;line-height:14px;padding:8px;box-sizing:border-box;transform:rotate(-8deg)}}
    </style></head><body><div class=cert>
      <div class=brand>CORZAAR · {status.replace('_', ' ').title()}</div>
      {status_banner}
      <h1>Certificate of Completion</h1>
      <p class=lead>This is to certify that</p>
      <h2>{name}</h2>
      <p class=lead>has successfully completed</p>
      <p class=course>{course_title}</p>
      <p class=meta>Awarded by {institute_name} · {issued_at}</p>
      {signatory_row}
      <div class=row>
        <div><strong>Certificate ID</strong>{cert_id}</div>
        <div><strong>Issued</strong>{issued_at}</div>
        <div><strong>Institute</strong>{institute_name}</div>
      </div>
      {qr_html}
      <div class=seal>CORZAAR<br>VERIFIED</div>
    </div></body></html>"""


def render_certificate_pdf(
    name: str,
    course_title: str,
    institute_name: str,
    cert_id: str,
    issued_at: str,
    style: str = "classic",
    accent: str = "#1E3A5F",
    signatory: str = "",
    verify_url: str = "",
) -> bytes:
    """Generate high-resolution landscape A4 PDF certificate using ReportLab."""
    buf = io.BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    is_bold = style == "bold"
    bg_hex = "#0F1E33" if is_bold else "#F7F9FC"
    card_hex = "#1E3A5F" if is_bold else "#FFFFFF"
    ink_hex = "#FFFFFF" if is_bold else "#0F1E33"
    muted_hex = "#DFF5EB" if is_bold else "#64748B"

    # Background
    c.setFillColor(HexColor(bg_hex))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Inner card
    margin = 22 * mm
    c.setFillColor(HexColor(card_hex))
    c.roundRect(margin, margin, w - 2 * margin, h - 2 * margin, 12, fill=1, stroke=0)

    # Border
    c.setStrokeColor(HexColor(accent))
    c.setLineWidth(1.4)
    c.roundRect(margin + 8, margin + 8, w - 2 * margin - 16, h - 2 * margin - 16, 8, fill=0, stroke=1)

    # Brand
    c.setFillColor(HexColor(accent))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(w / 2, h - margin - 22, "CORZAAR  ·  CERTIFICATE OF COMPLETION")

    # Title
    c.setFillColor(HexColor(accent))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(w / 2, h - margin - 66, "Certificate of Completion")

    # Lead
    c.setFillColor(HexColor(muted_hex))
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, h - margin - 92, "This is to certify that")

    # Name
    c.setFillColor(HexColor(ink_hex))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(w / 2, h - margin - 128, name)

    # Lead
    c.setFillColor(HexColor(muted_hex))
    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, h - margin - 152, "has successfully completed")

    # Course
    c.setFillColor(HexColor(accent))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, h - margin - 178, course_title)

    # Meta
    c.setFillColor(HexColor(muted_hex))
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, h - margin - 202, f"Awarded by {institute_name}  ·  {issued_at}")

    # Signatory (optional)
    if signatory:
        c.setFillColor(HexColor(muted_hex))
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(w / 2, h - margin - 224, f"Authorised · {signatory}")

    # Footer row
    footer_y = margin + 34
    for i, (label, value) in enumerate([("CERTIFICATE ID", cert_id), ("ISSUED", issued_at), ("INSTITUTE", institute_name)]):
        x = margin + 40 + i * ((w - 2 * margin - 80) / 3)
        c.setFillColor(HexColor(muted_hex))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, footer_y + 14, label)
        c.setFillColor(HexColor(ink_hex))
        c.setFont("Helvetica", 11)
        c.drawString(x, footer_y, value)

    # Verify URL
    if verify_url:
        c.setFillColor(HexColor(muted_hex))
        c.setFont("Helvetica", 8)
        c.drawCentredString(w / 2, margin + 14, f"Verify at: {verify_url}")

    # Seal
    c.setFillColor(HexColor("#0EA5A0"))
    c.circle(w - margin - 48, margin + 60, 30, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(w - margin - 48, margin + 66, "CORZAAR")
    c.drawCentredString(w - margin - 48, margin + 56, "VERIFIED")

    c.showPage()
    c.save()
    return buf.getvalue()


async def issue_or_pend_certificate(
    user: Dict[str, Any],
    enrollment: Dict[str, Any],
    course: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Create a Certificate record if not already issued; returns the certificate or None."""
    existing = await db.certificates.find_one({"enrollment_id": enrollment["id"]}, {"_id": 0})
    if existing:
        return existing

    cfg = course.get("certificate_config") or {}
    if not cfg.get("enabled", True):
        return None

    institute_id = course.get("institute_id", "")
    cert_id_str = gen_cert_id(institute_id, course["id"])
    while await db.certificates.find_one({"certificate_id": cert_id_str}):
        cert_id_str = gen_cert_id(institute_id, course["id"])

    method = (cfg.get("issue_method") or "automatic").lower()
    status = "issued" if method == "automatic" else "pending_approval"

    doc = {
        "id": str(uuid.uuid4()),
        "certificate_id": cert_id_str,
        "student_id": user["id"],
        "student_name": user.get("full_name") or "CORZAAR learner",
        "course_id": course["id"],
        "course_title": course.get("title") or "CORZAAR course",
        "institute_id": institute_id,
        "enrollment_id": enrollment["id"],
        "template_id": cfg.get("template_id"),
        "certificate_name": cfg.get("certificate_name") or "Certificate of Completion",
        "merchant_id": course.get("merchant_id"),
        "completion_date": now(),
        "issue_date": now() if status == "issued" else None,
        "issue_method": method,
        "status": status,  # pending_approval | issued | revoked
        "created_at": now(),
    }
    await db.certificates.insert_one(doc.copy())

    if status == "issued":
        await db.enrollments.update_one(
            {"id": enrollment["id"]},
            {"$set": {"certificate_id": cert_id_str, "completed_at": doc["completion_date"]}},
        )
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "title": "Certificate ready",
            "body": f"Your certificate for {doc['course_title']} is ready.",
            "kind": "cert",
            "created_at": now(),
            "read": False,
        })
    else:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "title": "Certificate pending approval",
            "body": f"Your completion for {doc['course_title']} is under merchant review.",
            "kind": "cert",
            "created_at": now(),
            "read": False,
        })
        if course.get("merchant_id"):
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": course["merchant_id"],
                "title": "Certificate awaiting approval",
                "body": f"{doc['student_name']} completed {doc['course_title']}.",
                "kind": "cert",
                "created_at": now(),
                "read": False,
            })
    return doc


async def verify_certificate(cert_id: str, request: Optional[Request] = None) -> Dict[str, Any]:
    """Public certificate verification by unique certificate ID."""
    cert = await db.certificates.find_one({"certificate_id": cert_id}, {"_id": 0})
    if not cert:
        # Legacy fallback: check enrollments.certificate_id
        enrollment = await db.enrollments.find_one({"certificate_id": cert_id}, {"_id": 0})
        if enrollment:
            student = await db.users.find_one({"id": enrollment["student_id"]}, {"_id": 0}) or {}
            course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0}) or {}
            institute = await db.institutes.find_one({"id": course.get("institute_id")}, {"_id": 0}) or {}
            return {
                "valid": True,
                "status": "issued",
                "certificate_id": cert_id,
                "student_name": student.get("full_name") or "CORZAAR learner",
                "course_title": course.get("title"),
                "institute_name": institute.get("name"),
                "issue_date": enrollment.get("completed_at"),
                "completion_date": enrollment.get("completed_at"),
            }
        return {"valid": False, "status": "invalid", "certificate_id": cert_id, "message": "Certificate not found"}

    valid = cert.get("status") == "issued"
    course = await db.courses.find_one({"id": cert["course_id"]}, {"_id": 0}) or {}
    institute = await db.institutes.find_one({"id": cert.get("institute_id")}, {"_id": 0}) or {}
    return {
        "valid": valid,
        "status": cert.get("status"),
        "certificate_id": cert_id,
        "student_name": cert.get("student_name"),
        "course_title": cert.get("course_title") or course.get("title"),
        "institute_name": institute.get("name"),
        "issue_date": cert.get("issue_date"),
        "completion_date": cert.get("completion_date"),
    }
