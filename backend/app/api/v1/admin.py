import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import db
from app.core.security import now, public, public_many
from app.dependencies.auth import require_roles
from app.models.merchant import PayoutRecord
from app.models.payment import CashoutAction
from app.services.audit_service import audit
from app.services.merchant_service import merchant_earnings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def admin_dashboard(user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    """Retrieve executive KPIs including total students, active institutes, pending approvals, and gross revenue."""
    revenue = 0.0
    for p in await db.payments.find({"status": "succeeded"}, {"_id": 0, "amount_total": 1, "amount": 1}).to_list(2000):
        if p.get("amount_total"):
            revenue += float(p["amount_total"]) / 100.0  # Stripe returns paise for INR
        else:
            revenue += float(p.get("amount") or 0)

    return {
        "total_students": await db.users.count_documents({"role": "student"}),
        "active_institutes": await db.institutes.count_documents({"status": "approved"}),
        "active_courses": await db.courses.count_documents({"status": "published"}),
        "pending_courses": await db.courses.count_documents({"status": "under_review"}),
        "pending_coupons": await db.coupons.count_documents({"status": "pending"}),
        "pending_refunds": await db.refunds.count_documents({"status": "pending"}),
        "revenue": revenue,
        "new_registrations": await db.merchant_registrations.count_documents({"status": "pending"}),
        "alerts": ["Review new institute applications", "Review pending courses & coupons", "Monitor refund requests"],
    }


@router.get("/institutes")
async def admin_institutes(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """List all institutes across all statuses."""
    return public_many(await db.institutes.find({}, {"_id": 0}).sort("status", 1).to_list(100))


@router.post("/institutes/{institute_id}/status")
async def institute_status(
    institute_id: str,
    status: Optional[str] = Query(default=None),
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Approve, reject, or suspend an institute."""
    final_status = status or (payload or {}).get("status")
    if not final_status or final_status not in ("approved", "rejected", "suspended", "pending"):
        raise HTTPException(status_code=400, detail="Invalid institute status")
    result = await db.institutes.update_one({"id": institute_id}, {"$set": {"status": final_status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Institute not found")
    await audit(user, f"Institute {final_status}", "Institutes", institute_id, institute_id)
    return {"id": institute_id, "status": final_status}


@router.get("/courses")
async def admin_courses(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """List all courses requiring administrative moderation."""
    return public_many(await db.courses.find({"status": {"$in": ["under_review", "published", "rejected"]}}, {"_id": 0}).sort("status", 1).to_list(200))


@router.post("/courses/{course_id}/status")
async def course_status(
    course_id: str,
    status: Optional[str] = Query(default=None),
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Publish, reject, or reset a course to under_review."""
    final_status = status or (payload or {}).get("status")
    if not final_status or final_status not in ("published", "rejected", "under_review"):
        raise HTTPException(status_code=400, detail="Invalid course status")
    result = await db.courses.update_one({"id": course_id}, {"$set": {"status": final_status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    await audit(user, f"Course {final_status}", "Courses", course_id, course_id)
    return {"id": course_id, "status": final_status}


@router.get("/coupons")
async def admin_coupons(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """List all merchant discount coupons for moderation."""
    rows = public_many(await db.coupons.find({}, {"_id": 0}).sort("status", 1).to_list(200))
    for row in rows:
        merchant = await db.users.find_one({"id": row.get("merchant_id")}, {"_id": 0, "full_name": 1, "mobile": 1})
        row["merchant"] = public(merchant)
    return rows


@router.post("/admin/coupons/{coupon_id}/status")
@router.post("/coupons/{coupon_id}/status")
async def coupon_status(
    coupon_id: str,
    status: str = Query(..., pattern="^(approved|rejected|pending)$"),
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Approve or reject a merchant discount coupon."""
    result = await db.coupons.update_one({"id": coupon_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    await audit(user, f"Coupon {status}", "Coupons", coupon_id, coupon_id)
    return {"id": coupon_id, "status": status}


@router.get("/refunds")
async def admin_refunds(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """List all student refund requests."""
    return public_many(await db.refunds.find({}, {"_id": 0}).sort("created_at", -1).to_list(200))


@router.post("/refunds/{refund_id}/action")
async def refund_action(
    refund_id: str,
    status: str = Query(..., pattern="^(approved|rejected|processed)$"),
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Approve, reject, or mark refund as processed."""
    refund = await db.refunds.find_one({"id": refund_id}, {"_id": 0})
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    await db.refunds.update_one({"id": refund_id}, {"$set": {"status": status, "resolved_at": now(), "resolved_by": user["id"]}})
    if status in ("approved", "processed"):
        await db.enrollments.update_one({"id": refund["enrollment_id"]}, {"$set": {"status": "refunded", "payment_status": "refunded"}})
    await audit(user, f"Refund {status}", "Refunds", refund.get("course_title", ""), refund_id)
    return {"id": refund_id, "status": status}


@router.get("/payouts")
async def admin_payouts(user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    """Get merchant payout ledgers and historical disbursements."""
    merchants = public_many(await db.users.find({"role": "merchant"}, {"_id": 0}).to_list(500))
    ledger: List[Dict[str, Any]] = []
    for m in merchants:
        earnings = await merchant_earnings(m["id"])
        institute = await db.institutes.find_one({"merchant_id": m["id"]}, {"_id": 0, "name": 1, "city": 1})
        ledger.append({
            "merchant_id": m["id"],
            "merchant_name": m.get("full_name") or m.get("mobile"),
            "institute": public(institute),
            **earnings,
        })
    history = public_many(await db.payouts.find({}, {"_id": 0}).sort("created_at", -1).to_list(200))
    return {"ledger": ledger, "history": history, "note": "Manual tracking in preview. After you deploy with live Stripe keys, upgrade to Stripe Connect for automated splits."}


@router.post("/payouts")
async def record_payout(
    payload: PayoutRecord,
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Record an instructor / merchant disbursement in the platform ledger."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    payout = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "status": "sent",
        "recorded_by": user["id"],
        "created_at": now(),
    }
    await db.payouts.insert_one(payout.copy())
    await audit(user, "Payout recorded", "Payouts", f"₹{payload.amount:.0f} to {payload.merchant_id}", payout["id"])
    return payout


@router.get("/cashouts")
async def admin_cashouts(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """List student UPI cashout requests."""
    return public_many(await db.cashouts.find({}, {"_id": 0}).sort("created_at", -1).to_list(200))


@router.post("/cashouts/{cashout_id}/action")
async def cashout_action(
    cashout_id: str,
    payload: CashoutAction,
    status: str = Query(..., pattern="^(approved|rejected|paid)$"),
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Approve, reject, or mark a student wallet cashout as paid."""
    cashout = await db.cashouts.find_one({"id": cashout_id}, {"_id": 0})
    if not cashout:
        raise HTTPException(status_code=404, detail="Cashout not found")
    if cashout["status"] in ("paid", "rejected"):
        raise HTTPException(status_code=400, detail="Cashout already resolved")

    updates: Dict[str, Any] = {
        "status": status,
        "resolved_at": now(),
        "resolved_by": user["id"],
        "reference": payload.reference,
    }
    if status == "rejected":
        # Refund the locked amount back to student wallet
        await db.users.update_one({"id": cashout["student_id"]}, {"$inc": {"wallet_balance": float(cashout["amount"])}})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": cashout["student_id"],
            "title": "Cashout rejected",
            "body": f"₹{cashout['amount']:.0f} has been returned to your wallet.",
            "kind": "cashout",
            "created_at": now(),
            "read": False,
        })
    elif status == "approved":
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": cashout["student_id"],
            "title": "Cashout approved",
            "body": f"₹{cashout['amount']:.0f} approved — payout in progress to {cashout['upi_id']}.",
            "kind": "cashout",
            "created_at": now(),
            "read": False,
        })
    elif status == "paid":
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": cashout["student_id"],
            "title": "Cashout paid",
            "body": f"₹{cashout['amount']:.0f} sent to {cashout['upi_id']}.",
            "kind": "cashout",
            "created_at": now(),
            "read": False,
        })

    await db.cashouts.update_one({"id": cashout_id}, {"$set": updates})
    await audit(user, f"Cashout {status}", "Cashouts", f"₹{cashout['amount']:.0f}", cashout_id)
    return {"id": cashout_id, "status": status}


@router.get("/certificates")
async def admin_certificates(user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    """Retrieve all platform certificates and templates with counts."""
    rows = public_many(await db.certificates.find({}, {"_id": 0}).sort("created_at", -1).to_list(500))
    templates = public_many(await db.certificate_templates.find({}, {"_id": 0}).to_list(200))
    counts = {"issued": 0, "pending_approval": 0, "revoked": 0, "total": len(rows)}
    for r in rows:
        st = r.get("status", "issued")
        counts[st] = counts.get(st, 0) + 1
    return {"certificates": rows, "templates": templates, "counts": counts}


@router.post("/certificates/{cert_id}/revoke")
async def admin_revoke_cert(
    cert_id: str,
    user: Dict[str, Any] = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    """Revoke an issued certificate and unlink it from the student's enrollment."""
    cert = await db.certificates.find_one({"id": cert_id}, {"_id": 0})
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    await db.certificates.update_one({"id": cert_id}, {"$set": {"status": "revoked", "revoked_by": user["id"], "revoked_at": now(), "revoke_reason": "Admin revocation"}})
    await db.enrollments.update_one({"id": cert["enrollment_id"]}, {"$unset": {"certificate_id": ""}})
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": cert["student_id"],
        "title": "Certificate revoked",
        "body": f"Your certificate for {cert.get('course_title', 'the course')} was revoked by CORZAAR admin.",
        "kind": "cert",
        "created_at": now(),
        "read": False,
    })
    await audit(user, "Certificate revoked", "Certificates", cert.get("course_title", ""), cert_id)
    return {"id": cert_id, "status": "revoked"}


@router.get("/audit-logs")
async def admin_audit_logs(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """Retrieve full platform audit trails."""
    rows = public_many(await db.activity_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100))
    return rows or [{"id": "seed-log", "action": "System ready", "module": "Platform", "role": "Admin", "created_at": now()}]


@router.get("/activity")
async def admin_activity(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    """Alias for audit logs."""
    return await admin_audit_logs(user)
