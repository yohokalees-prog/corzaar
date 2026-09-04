"""Iteration 5 backend tests: PDF certificate + share links, session reminders,
merchant insights, wallet cashout (student + admin actions), regression for iter4."""
import os
import re
import uuid
import random
from datetime import date, timedelta

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or "https://corzaar-staging.preview.emergentagent.com").rstrip("/")


# ---------- Helpers ----------
def _mob() -> str:
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


def _student_login(name: str = "TEST Student", ref_code: str = "") -> dict:
    m = _mob()
    r = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"mobile": m, "role": "student"})
    assert r.status_code == 200, r.text
    body = {"mobile": m, "otp": "123456", "role": "student", "full_name": name}
    if ref_code:
        body["referral_code"] = ref_code
    r = requests.post(f"{BASE_URL}/api/auth/verify-otp", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"token": d["access_token"], "user": d["user"], "mobile": m}


def _merchant_login(name: str = "TEST Merchant") -> dict:
    m = _mob()
    requests.post(f"{BASE_URL}/api/auth/send-otp", json={"mobile": m, "role": "merchant"})
    r = requests.post(f"{BASE_URL}/api/auth/verify-otp",
                     json={"mobile": m, "otp": "123456", "role": "merchant", "full_name": name})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"token": d["access_token"], "user": d["user"], "mobile": m}


def _admin_login() -> str:
    requests.post(f"{BASE_URL}/api/auth/admin-login",
                  json={"email": "admin@corzaar.com", "password": "Admin@123"})
    r = requests.post(f"{BASE_URL}/api/auth/admin-verify",
                      json={"email": "admin@corzaar.com", "otp": "123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _complete_free_course(student: dict, course_id: str = "course-marketing") -> str:
    """Enroll student in a free course, mark 100% progress, return enrollment id."""
    er = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(student["token"]),
                       json={"course_id": course_id})
    assert er.status_code == 200, er.text
    eid = er.json()["id"]
    cr = requests.get(f"{BASE_URL}/api/courses/{course_id}").json()
    curr = cr["course"]["curriculum"]
    pr = requests.post(f"{BASE_URL}/api/me/enrollments/{eid}/progress",
                       headers=_h(student["token"]), json={"completed": curr})
    assert pr.status_code == 200
    assert pr.json().get("certificate_id")
    return eid


def _seed_wallet(student: dict, target: int = 600) -> int:
    """Bump student's wallet by referring `target//200` friends who enroll in the free course."""
    ref = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(student["token"])).json()
    code = ref["code"]
    n = max(1, (target + 199) // 200)
    for _ in range(n):
        friend = _student_login("TEST Ref Friend")
        r = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(friend["token"]),
                          json={"course_id": "course-marketing", "referral_code": code})
        assert r.status_code == 200, r.text
    ref2 = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(student["token"])).json()
    return int(ref2["wallet_balance"])


# =========================================================
# 1) PDF certificate
# =========================================================
class TestCertificatePdf:
    def test_pdf_404_before_completion(self):
        s = _student_login("PDF Early")
        er = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(s["token"]),
                           json={"course_id": "course-marketing"})
        eid = er.json()["id"]
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/certificate.pdf",
                         headers=_h(s["token"]))
        assert r.status_code == 404

    def test_pdf_bearer_and_query_auth(self):
        s = _student_login("PDF Ready")
        eid = _complete_free_course(s)

        # via Bearer
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/certificate.pdf",
                         headers=_h(s["token"]))
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert "CZ-CERT-" in r.headers.get("content-disposition", "")

        # via ?auth= query
        r2 = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/certificate.pdf?auth={s['token']}")
        assert r2.status_code == 200
        assert r2.headers["content-type"].startswith("application/pdf")
        assert r2.content[:4] == b"%PDF"

    def test_pdf_unauth(self):
        s = _student_login("PDF Auth")
        eid = _complete_free_course(s)
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/certificate.pdf")
        assert r.status_code in (401, 403)


# =========================================================
# 2) Share links
# =========================================================
class TestCertificateShare:
    def test_share_404_before_completion(self):
        s = _student_login("Share Early")
        er = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(s["token"]),
                           json={"course_id": "course-marketing"})
        eid = er.json()["id"]
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/share", headers=_h(s["token"]))
        assert r.status_code == 404

    def test_share_returns_all_channels(self):
        s = _student_login("Share Ready")
        eid = _complete_free_course(s)
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/share", headers=_h(s["token"]))
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("certificate_url", "pdf_url", "linkedin", "twitter", "whatsapp"):
            assert k in j and j[k], f"missing/empty {k}: {j}"
        assert j["pdf_url"].endswith(".pdf")
        assert "www.linkedin.com/sharing" in j["linkedin"]
        assert "twitter.com/intent/tweet" in j["twitter"]
        assert "wa.me" in j["whatsapp"]
        # cert_url should be encoded into the share targets
        assert j["certificate_url"].split("/api/")[0] in j["linkedin"] or \
               "certificate" in j["linkedin"]


# =========================================================
# 3) Session reminders in /me/notifications
# =========================================================
class TestSessionReminders:
    @pytest.fixture(scope="class")
    def merchant_course(self):
        admin = _admin_login()
        m = _merchant_login("Reminder Merchant")
        insts = requests.get(f"{BASE_URL}/api/admin/institutes", headers=_h(admin)).json()
        my_inst = next(i for i in insts if i.get("merchant_id") == m["user"]["id"])
        requests.post(f"{BASE_URL}/api/admin/institutes/{my_inst['id']}/status?status=approved",
                      headers=_h(admin))
        # create paid course + publish; use 100% coupon so student's enrollment becomes active
        cr = requests.post(f"{BASE_URL}/api/merchant/courses", headers=_h(m["token"]),
                           json={"title": "TEST_Reminder_Course", "description": "r",
                                 "category": "Technology", "fees": 4000, "duration": "1 week",
                                 "curriculum": ["Intro"]})
        cid = cr.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/courses/{cid}/status?status=published",
                      headers=_h(admin))
        cp = requests.post(f"{BASE_URL}/api/merchant/coupons", headers=_h(m["token"]),
                           json={"code": f"REMFREE{uuid.uuid4().hex[:6].upper()}",
                                 "description": "", "discount_percent": 100, "course_id": cid})
        code = cp.json()["code"]
        cpid = cp.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/coupons/{cpid}/status?status=approved",
                      headers=_h(admin))
        return {"merchant": m, "admin": admin, "course_id": cid, "coupon": code}

    def test_reminder_for_today_session(self, merchant_course):
        m = merchant_course["merchant"]
        today = date.today()
        # Schedule includes every weekday so today is guaranteed
        full_sched = "Mon Tue Wed Thu Fri Sat Sun"
        br = requests.post(f"{BASE_URL}/api/merchant/batches", headers=_h(m["token"]),
                           json={"course_id": merchant_course["course_id"],
                                 "schedule": full_sched, "capacity": 10,
                                 "coordinator": "TEST Rem",
                                 "start_date": today.isoformat(),
                                 "end_date": (today + timedelta(days=2)).isoformat()})
        assert br.status_code == 200, br.text
        sessions = br.json()["sessions"]
        session_dates = [s["date"] for s in sessions]
        assert today.isoformat() in session_dates

        # Enroll a student in this course via 100% coupon → active
        student = _student_login("Rem Student")
        er = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(student["token"]),
                           json={"course_id": merchant_course["course_id"],
                                 "coupon_code": merchant_course["coupon"]})
        assert er.status_code == 200, er.text
        assert er.json()["status"] == "active"

        # Fetch notifications — should contain a reminder for today
        nr = requests.get(f"{BASE_URL}/api/me/notifications", headers=_h(student["token"]))
        assert nr.status_code == 200
        items = nr.json()
        reminders = [n for n in items if n.get("kind") == "reminder"]
        assert reminders, f"no reminders found in {items}"
        today_rem = [r for r in reminders if today.isoformat() in (r.get("body") or "")]
        assert today_rem, f"no today reminder: {reminders}"
        rem = today_rem[0]
        assert "TEST_Reminder_Course" in rem["body"], rem
        assert rem["title"] in ("Class today", "Class tomorrow")

    def test_non_student_gets_no_reminders(self, merchant_course):
        m = merchant_course["merchant"]
        nr = requests.get(f"{BASE_URL}/api/me/notifications", headers=_h(m["token"]))
        assert nr.status_code == 200
        assert not any(n.get("kind") == "reminder" for n in nr.json())


# =========================================================
# 4) Merchant insights
# =========================================================
class TestMerchantInsights:
    def test_insights_shape_and_role(self):
        admin = _admin_login()
        m = _merchant_login("Insight Merchant")
        insts = requests.get(f"{BASE_URL}/api/admin/institutes", headers=_h(admin)).json()
        my_inst = next(i for i in insts if i.get("merchant_id") == m["user"]["id"])
        requests.post(f"{BASE_URL}/api/admin/institutes/{my_inst['id']}/status?status=approved",
                      headers=_h(admin))
        cr = requests.post(f"{BASE_URL}/api/merchant/courses", headers=_h(m["token"]),
                           json={"title": "TEST_Insight_Course", "description": "i",
                                 "category": "Business", "fees": 2000, "duration": "2 weeks",
                                 "curriculum": ["Alpha", "Beta", "Gamma"]})
        cid = cr.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/courses/{cid}/status?status=published",
                      headers=_h(admin))
        # 100% coupon for free active enrollments
        cp = requests.post(f"{BASE_URL}/api/merchant/coupons", headers=_h(m["token"]),
                           json={"code": f"INSFREE{uuid.uuid4().hex[:6].upper()}",
                                 "description": "", "discount_percent": 100, "course_id": cid})
        code = cp.json()["code"]
        cpid = cp.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/coupons/{cpid}/status?status=approved",
                      headers=_h(admin))

        # Two students enroll, one completes 2/3 items, one completes 1/3
        s1 = _student_login("Ins A")
        s2 = _student_login("Ins B")
        for s, completed in [(s1, ["Alpha", "Beta"]), (s2, ["Alpha"])]:
            r = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(s["token"]),
                              json={"course_id": cid, "coupon_code": code})
            assert r.status_code == 200
            eid = r.json()["id"]
            requests.post(f"{BASE_URL}/api/me/enrollments/{eid}/progress",
                          headers=_h(s["token"]), json={"completed": completed})
            # add a 5-star review
            requests.post(f"{BASE_URL}/api/reviews", headers=_h(s["token"]),
                          json={"target_type": "courses", "target_id": cid,
                                "rating": 5, "text": "great"})

        # Merchant fetches insights
        r = requests.get(f"{BASE_URL}/api/merchant/insights", headers=_h(m["token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data.keys()) >= {"rating_trend", "top_courses", "curriculum_dropoff"}

        # rating_trend: week + average + count
        assert isinstance(data["rating_trend"], list)
        assert len(data["rating_trend"]) >= 1
        wk = data["rating_trend"][0]
        assert {"week", "average", "count"} <= set(wk.keys())
        assert wk["count"] >= 2 and 0 <= wk["average"] <= 5

        # top_courses ≤5 and includes our course
        assert isinstance(data["top_courses"], list)
        assert len(data["top_courses"]) <= 5
        titles = [c["title"] for c in data["top_courses"]]
        assert "TEST_Insight_Course" in titles
        tc = next(c for c in data["top_courses"] if c["title"] == "TEST_Insight_Course")
        assert {"id", "title", "rating", "reviews_count", "students"} <= set(tc.keys())

        # curriculum_dropoff — items[]:{item,completed,pct}
        cdo = next(c for c in data["curriculum_dropoff"] if c["id"] == cid)
        assert cdo["enrolled"] == 2
        items = {i["item"]: i for i in cdo["items"]}
        assert items["Alpha"]["completed"] == 2 and items["Alpha"]["pct"] == 100.0
        assert items["Beta"]["completed"] == 1 and items["Beta"]["pct"] == 50.0
        assert items["Gamma"]["completed"] == 0 and items["Gamma"]["pct"] == 0.0

        # Role gating: student → 403
        student_tok = s1["token"]
        r = requests.get(f"{BASE_URL}/api/merchant/insights", headers=_h(student_tok))
        assert r.status_code == 403

        # Admin → 403 (merchant-only)
        r = requests.get(f"{BASE_URL}/api/merchant/insights", headers=_h(admin))
        assert r.status_code == 403


# =========================================================
# 5) Cashout request validation
# =========================================================
class TestCashoutRequest:
    def test_min_amount_rejection(self):
        s = _student_login("Cash Min")
        _seed_wallet(s, 600)
        r = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                          json={"upi_id": "min@upi", "amount": 100})
        assert r.status_code == 400
        assert "Minimum" in r.text or "500" in r.text

    def test_over_balance_rejection(self):
        s = _student_login("Cash Over")
        _seed_wallet(s, 600)
        r = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                          json={"upi_id": "over@upi", "amount": 5000})
        assert r.status_code == 400
        assert "balance" in r.text.lower()

    def test_invalid_upi_rejection(self):
        s = _student_login("Cash UPI")
        _seed_wallet(s, 600)
        r = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                          json={"upi_id": "noatsign", "amount": 500})
        assert r.status_code == 400
        assert "UPI" in r.text or "upi" in r.text

    def test_successful_cashout_creates_notif_and_deducts_wallet(self):
        s = _student_login("Cash OK")
        bal_before = _seed_wallet(s, 600)
        r = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                          json={"upi_id": "test@upi", "amount": 500})
        assert r.status_code == 200, r.text
        co = r.json()
        assert co["status"] == "pending"
        assert co["amount"] == 500
        assert co["upi_id"] == "test@upi"

        # wallet dropped by 500
        ref = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(s["token"])).json()
        assert ref["wallet_balance"] == bal_before - 500

        # notification present
        notif = requests.get(f"{BASE_URL}/api/me/notifications", headers=_h(s["token"])).json()
        assert any(n.get("kind") == "cashout" for n in notif)

    def test_non_student_cannot_request(self):
        m = _merchant_login()
        r = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(m["token"]),
                          json={"upi_id": "m@upi", "amount": 500})
        assert r.status_code == 403


# =========================================================
# 6) Cashout listing
# =========================================================
class TestCashoutList:
    def test_my_and_admin_lists(self):
        admin = _admin_login()
        s = _student_login("Cash List")
        _seed_wallet(s, 600)
        cr = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                           json={"upi_id": "list@upi", "amount": 500})
        assert cr.status_code == 200, cr.text
        cid = cr.json()["id"]

        mine = requests.get(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]))
        assert mine.status_code == 200
        assert any(c["id"] == cid for c in mine.json())

        all_c = requests.get(f"{BASE_URL}/api/admin/cashouts", headers=_h(admin))
        assert all_c.status_code == 200
        assert any(c["id"] == cid for c in all_c.json())

        # student cannot list all
        r = requests.get(f"{BASE_URL}/api/admin/cashouts", headers=_h(s["token"]))
        assert r.status_code == 403


# =========================================================
# 7 + 8) Admin actions + end-to-end refund/paid
# =========================================================
class TestCashoutAdminActions:
    def test_reject_refunds_wallet_and_already_resolved_400(self):
        admin = _admin_login()
        s = _student_login("Cash Reject")
        bal = _seed_wallet(s, 600)
        cr = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                           json={"upi_id": "r@upi", "amount": 500})
        assert cr.status_code == 200
        cid = cr.json()["id"]

        # wallet dropped by 500
        r_ref = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(s["token"])).json()
        assert r_ref["wallet_balance"] == bal - 500

        # reject
        r = requests.post(f"{BASE_URL}/api/admin/cashouts/{cid}/action?status=rejected",
                          headers=_h(admin), json={"reference": "invalid upi"})
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

        # wallet restored
        r_ref2 = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(s["token"])).json()
        assert r_ref2["wallet_balance"] == bal

        # notification 'rejected' present
        notif = requests.get(f"{BASE_URL}/api/me/notifications", headers=_h(s["token"])).json()
        assert any(n.get("kind") == "cashout" and "reject" in (n.get("body", "") + n.get("title", "")).lower()
                   for n in notif)

        # already resolved → 400
        r2 = requests.post(f"{BASE_URL}/api/admin/cashouts/{cid}/action?status=paid",
                           headers=_h(admin), json={"reference": "ref-x"})
        assert r2.status_code == 400

    def test_paid_flow_keeps_wallet_deducted_with_reference_and_audit(self):
        admin = _admin_login()
        s = _student_login("Cash Paid")
        bal = _seed_wallet(s, 600)
        cr = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                           json={"upi_id": "paid@upi", "amount": 500})
        cid = cr.json()["id"]
        assert cr.status_code == 200

        r = requests.post(f"{BASE_URL}/api/admin/cashouts/{cid}/action?status=paid",
                          headers=_h(admin), json={"reference": "UTR-TESTPAID-001"})
        assert r.status_code == 200
        assert r.json()["status"] == "paid"

        # wallet stays deducted
        rr = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(s["token"])).json()
        assert rr["wallet_balance"] == bal - 500

        # cashout record has reference + resolved fields
        mine = requests.get(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"])).json()
        my = next(c for c in mine if c["id"] == cid)
        assert my["status"] == "paid"
        assert my["reference"] == "UTR-TESTPAID-001"

        # audit log has both entries (request + paid) for this cashout
        alr = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=_h(admin))
        assert alr.status_code == 200
        entries = [a for a in alr.json() if a.get("target_id") == cid]
        actions = {a.get("action", "").lower() for a in entries}
        assert any("request" in a for a in actions), actions
        assert any("paid" in a for a in actions), actions

    def test_non_admin_cannot_action(self):
        s = _student_login("Cash NonAdmin")
        _seed_wallet(s, 600)
        cr = requests.post(f"{BASE_URL}/api/me/cashouts", headers=_h(s["token"]),
                           json={"upi_id": "n@upi", "amount": 500})
        cid = cr.json()["id"]
        r = requests.post(f"{BASE_URL}/api/admin/cashouts/{cid}/action?status=paid",
                          headers=_h(s["token"]), json={"reference": ""})
        assert r.status_code == 403


# =========================================================
# 9) Regression from iteration 4 core
# =========================================================
class TestIter4Regression:
    def test_stripe_checkout_paid_course_returns_url(self):
        s = _student_login("Reg Stripe")
        r = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(s["token"]),
                          json={"course_id": "course-product"})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        assert r.json()["status"] == "pending_payment"
        # request Stripe hosted checkout URL
        ck = requests.post(f"{BASE_URL}/api/payments/checkout", headers=_h(s["token"]),
                           json={"enrollment_id": eid})
        assert ck.status_code == 200, ck.text
        url = ck.json().get("checkout_url", "")
        assert "stripe.com" in url, url

    def test_referral_and_wallet_intact(self):
        s = _student_login("Reg Ref")
        ref = requests.get(f"{BASE_URL}/api/me/referrals", headers=_h(s["token"]))
        assert ref.status_code == 200
        assert ref.json()["code"].startswith("REF")
        assert ref.json()["reward_per_referral"] == 200

    def test_batches_auto_sessions_still_works(self):
        admin = _admin_login()
        m = _merchant_login("Reg Batch Merch")
        insts = requests.get(f"{BASE_URL}/api/admin/institutes", headers=_h(admin)).json()
        my_inst = next(i for i in insts if i.get("merchant_id") == m["user"]["id"])
        requests.post(f"{BASE_URL}/api/admin/institutes/{my_inst['id']}/status?status=approved",
                      headers=_h(admin))
        cr = requests.post(f"{BASE_URL}/api/merchant/courses", headers=_h(m["token"]),
                           json={"title": "TEST_Reg_Batch", "description": "x",
                                 "category": "Tech", "fees": 100, "duration": "1w",
                                 "curriculum": ["a"]})
        cid = cr.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/courses/{cid}/status?status=published",
                      headers=_h(admin))
        r = requests.post(f"{BASE_URL}/api/merchant/batches", headers=_h(m["token"]),
                          json={"course_id": cid, "schedule": "Mon Wed", "capacity": 10,
                                "coordinator": "Reg", "start_date": "2026-02-02",
                                "end_date": "2026-02-15"})
        assert r.status_code == 200
        assert len(r.json()["sessions"]) == 4

    def test_admin_payouts_ledger(self):
        admin = _admin_login()
        r = requests.get(f"{BASE_URL}/api/admin/payouts", headers=_h(admin))
        assert r.status_code == 200
        j = r.json()
        assert "ledger" in j or "merchants" in j or isinstance(j, dict)

    def test_certificate_html_still_works(self):
        s = _student_login("Reg Cert")
        eid = _complete_free_course(s)
        r = requests.get(f"{BASE_URL}/api/me/enrollments/{eid}/certificate", headers=_h(s["token"]))
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_reviews_still_work(self):
        admin = _admin_login()
        m = _merchant_login("Reg Rev Merch")
        insts = requests.get(f"{BASE_URL}/api/admin/institutes", headers=_h(admin)).json()
        my_inst = next(i for i in insts if i.get("merchant_id") == m["user"]["id"])
        requests.post(f"{BASE_URL}/api/admin/institutes/{my_inst['id']}/status?status=approved",
                      headers=_h(admin))
        cr = requests.post(f"{BASE_URL}/api/merchant/courses", headers=_h(m["token"]),
                           json={"title": "TEST_Reg_Review", "description": "r",
                                 "category": "Business", "fees": 500, "duration": "1w",
                                 "curriculum": ["x"]})
        cid = cr.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/courses/{cid}/status?status=published",
                      headers=_h(admin))
        cp = requests.post(f"{BASE_URL}/api/merchant/coupons", headers=_h(m["token"]),
                           json={"code": f"REGREV{uuid.uuid4().hex[:6].upper()}",
                                 "description": "", "discount_percent": 100, "course_id": cid})
        code = cp.json()["code"]
        cpid = cp.json()["id"]
        requests.post(f"{BASE_URL}/api/admin/coupons/{cpid}/status?status=approved",
                      headers=_h(admin))
        s = _student_login("Reg Reviewer")
        er = requests.post(f"{BASE_URL}/api/enrollments", headers=_h(s["token"]),
                           json={"course_id": cid, "coupon_code": code})
        assert er.status_code == 200 and er.json()["status"] == "active"
        rv = requests.post(f"{BASE_URL}/api/reviews", headers=_h(s["token"]),
                           json={"target_type": "courses", "target_id": cid,
                                 "rating": 4, "text": "regression review"})
        assert rv.status_code == 200
