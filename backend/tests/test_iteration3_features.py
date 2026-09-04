"""Backend tests for iteration 3: Stripe checkout, coupons, courses approval, batches, ratings, refunds, admin insights."""
import os
import time
import uuid

import pytest
import requests


BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://corzaar-staging.preview.emergentagent.com"
).rstrip("/")


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def http():
    return requests.Session()


def _auth(http, mobile, role):
    r = http.post(f"{BASE_URL}/api/auth/verify-otp", json={"mobile": mobile, "otp": "123456", "role": role})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()["user"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def student(http):
    tok, u = _auth(http, "9" + uuid.uuid4().hex[:9], "student")
    return {"token": tok, "user": u}


@pytest.fixture(scope="module")
def student2(http):
    tok, u = _auth(http, "9" + uuid.uuid4().hex[:9], "student")
    return {"token": tok, "user": u}


@pytest.fixture(scope="module")
def merchant(http):
    tok, u = _auth(http, "8" + uuid.uuid4().hex[:9], "merchant")
    return {"token": tok, "user": u}


@pytest.fixture(scope="module")
def admin(http):
    login = http.post(f"{BASE_URL}/api/auth/admin-login", json={"email": "admin@corzaar.com", "password": "Admin@123"})
    assert login.status_code == 200
    verify = http.post(f"{BASE_URL}/api/auth/admin-verify", json={"email": "admin@corzaar.com", "otp": "123456"})
    assert verify.status_code == 200
    return {"token": verify.json()["access_token"], "user": verify.json()["user"]}


# ---------- Regression: existing endpoints ----------
class TestRegression:
    def test_home(self, http):
        r = http.get(f"{BASE_URL}/api/home")
        assert r.status_code == 200
        assert r.json()["courses"] and r.json()["institutes"]

    def test_courses(self, http):
        r = http.get(f"{BASE_URL}/api/courses")
        assert r.status_code == 200 and len(r.json()) >= 1

    def test_course_detail(self, http):
        r = http.get(f"{BASE_URL}/api/courses/course-product")
        assert r.status_code == 200 and r.json()["course"]["id"] == "course-product"

    def test_me(self, http, student):
        r = http.get(f"{BASE_URL}/api/me", headers=_hdr(student["token"]))
        assert r.status_code == 200 and r.json()["id"] == student["user"]["id"]

    def test_lists_cart_favorites(self, http, student):
        r = http.get(f"{BASE_URL}/api/me/lists", headers=_hdr(student["token"]))
        assert r.status_code == 200
        add = http.post(f"{BASE_URL}/api/me/cart", headers=_hdr(student["token"]), json={"course_id": "course-product"})
        assert add.status_code == 200 and "course-product" in add.json()["cart"]
        fav = http.post(f"{BASE_URL}/api/me/favorites", headers=_hdr(student["token"]), json={"course_id": "course-product"})
        assert fav.status_code == 200 and "course-product" in fav.json()["favorites"]

    def test_otp_send(self, http):
        r = http.post(f"{BASE_URL}/api/auth/send-otp", json={"mobile": "9999999999", "role": "student"})
        assert r.status_code == 200

    def test_admin_dashboard(self, http, admin):
        r = http.get(f"{BASE_URL}/api/admin/dashboard", headers=_hdr(admin["token"]))
        assert r.status_code == 200
        for key in ["total_students", "pending_courses", "pending_coupons", "pending_refunds"]:
            assert key in r.json(), f"missing {key}"


# ---------- Free enrollment ----------
class TestFreeEnrollment:
    def test_free_course_auto_active(self, http, student):
        # course-marketing has fees=0
        r = http.post(f"{BASE_URL}/api/enrollments", headers=_hdr(student["token"]), json={"course_id": "course-marketing"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "active"
        assert data["payment_status"] == "paid"
        assert data["amount"] == 0


# ---------- Merchant coupons + admin approval ----------
class TestCouponsFlow:
    coupon_id = None
    coupon_code = None

    def test_create_coupon_pending(self, http, merchant):
        code = "TEST" + uuid.uuid4().hex[:6].upper()
        TestCouponsFlow.coupon_code = code
        r = http.post(f"{BASE_URL}/api/merchant/coupons", headers=_hdr(merchant["token"]),
                      json={"code": code, "description": "test", "discount_percent": 20})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        TestCouponsFlow.coupon_id = r.json()["id"]

    def test_duplicate_coupon_rejected(self, http, merchant):
        r = http.post(f"{BASE_URL}/api/merchant/coupons", headers=_hdr(merchant["token"]),
                      json={"code": TestCouponsFlow.coupon_code, "description": "dup", "discount_percent": 10})
        assert r.status_code == 400

    def test_validate_pending_coupon_rejected(self, http, student):
        r = http.post(f"{BASE_URL}/api/coupons/validate", headers=_hdr(student["token"]),
                      json={"code": TestCouponsFlow.coupon_code, "course_id": "course-product"})
        assert r.status_code == 400  # not yet approved

    def test_admin_approves_coupon(self, http, admin):
        r = http.post(
            f"{BASE_URL}/api/admin/coupons/{TestCouponsFlow.coupon_id}/status",
            headers=_hdr(admin["token"]),
            params={"status": "approved"},
        )
        assert r.status_code == 200 and r.json()["status"] == "approved"

    def test_validate_approved_coupon(self, http, student):
        # Note: this coupon has merchant_id but no matching course merchant, so it will fail with
        # "Coupon is not valid for this course". Use an admin-controlled coupon with no merchant_id.
        # Instead, we validate that the endpoint accepts the coupon code (server-side match).
        r = http.post(f"{BASE_URL}/api/coupons/validate", headers=_hdr(student["token"]),
                      json={"code": TestCouponsFlow.coupon_code, "course_id": "course-product"})
        # course-product has merchant_id=None; coupon has merchant_id=merchant["id"] -> should be rejected
        assert r.status_code == 400


class TestCouponForMerchantCourse:
    """Full flow: merchant creates course -> admin publishes -> student enrolls -> coupon applies."""
    course_id = None
    coupon_id = None
    coupon_code = None

    def test_merchant_creates_course_under_review(self, http, merchant):
        r = http.post(f"{BASE_URL}/api/merchant/courses", headers=_hdr(merchant["token"]),
                      json={"title": "TEST_MerchantCourse", "description": "test", "category": "Design",
                            "fees": 1000, "duration": "4 weeks", "curriculum": ["A", "B"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "under_review"
        TestCouponForMerchantCourse.course_id = data["id"]

    def test_under_review_not_in_public_list(self, http):
        r = http.get(f"{BASE_URL}/api/courses")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert TestCouponForMerchantCourse.course_id not in ids

    def test_admin_publishes_course(self, http, admin):
        r = http.post(
            f"{BASE_URL}/api/admin/courses/{TestCouponForMerchantCourse.course_id}/status",
            headers=_hdr(admin["token"]),
            params={"status": "published"},
        )
        assert r.status_code == 200 and r.json()["status"] == "published"

    def test_published_now_visible(self, http):
        r = http.get(f"{BASE_URL}/api/courses")
        ids = [c["id"] for c in r.json()]
        assert TestCouponForMerchantCourse.course_id in ids

    def test_merchant_create_and_admin_approve_coupon(self, http, merchant, admin):
        code = "MC" + uuid.uuid4().hex[:6].upper()
        TestCouponForMerchantCourse.coupon_code = code
        r = http.post(f"{BASE_URL}/api/merchant/coupons", headers=_hdr(merchant["token"]),
                      json={"code": code, "description": "test", "discount_percent": 25})
        assert r.status_code == 200
        TestCouponForMerchantCourse.coupon_id = r.json()["id"]
        r2 = http.post(f"{BASE_URL}/api/admin/coupons/{TestCouponForMerchantCourse.coupon_id}/status",
                       headers=_hdr(admin["token"]), params={"status": "approved"})
        assert r2.status_code == 200

    def test_validate_approved_coupon_for_merchant_course(self, http, student):
        r = http.post(f"{BASE_URL}/api/coupons/validate", headers=_hdr(student["token"]),
                      json={"code": TestCouponForMerchantCourse.coupon_code,
                            "course_id": TestCouponForMerchantCourse.course_id})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["discount_percent"] == 25
        assert data["discount"] == 250.0
        assert data["final"] == 750.0

    def test_enrollment_with_coupon(self, http, student):
        r = http.post(f"{BASE_URL}/api/enrollments", headers=_hdr(student["token"]),
                      json={"course_id": TestCouponForMerchantCourse.course_id,
                            "coupon_code": TestCouponForMerchantCourse.coupon_code})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["original_amount"] == 1000.0
        assert data["discount"] == 250.0
        assert data["amount"] == 750.0
        assert data["coupon_code"] == TestCouponForMerchantCourse.coupon_code
        assert data["status"] == "pending_payment"


# ---------- Stripe checkout ----------
class TestStripeCheckout:
    session_id = None
    enrollment_id = None

    def test_checkout_creates_stripe_session(self, http, student):
        # Fresh student to avoid re-enrollment noise
        tok, u = _auth(http, "9" + uuid.uuid4().hex[:9], "student")
        enr = http.post(f"{BASE_URL}/api/enrollments", headers=_hdr(tok),
                        json={"course_id": "course-product"})  # fees 14999
        assert enr.status_code == 200
        assert enr.json()["status"] == "pending_payment"
        TestStripeCheckout.enrollment_id = enr.json()["id"]
        TestStripeCheckout._tok = tok

        r = http.post(f"{BASE_URL}/api/payments/checkout", headers=_hdr(tok),
                      json={"enrollment_id": enr.json()["id"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data and data["checkout_url"].startswith("https://checkout.stripe.com/"), data
        assert "session_id" in data and data["session_id"]
        TestStripeCheckout.session_id = data["session_id"]

    def test_payment_status_pending(self, http):
        r = http.get(
            f"{BASE_URL}/api/payments/status/{TestStripeCheckout.session_id}",
            headers=_hdr(TestStripeCheckout._tok),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["session_id"] == TestStripeCheckout.session_id
        assert data["status"] == "pending"
        assert data["enrollment_id"] == TestStripeCheckout.enrollment_id

    def test_payment_status_idempotent(self, http):
        r1 = http.get(f"{BASE_URL}/api/payments/status/{TestStripeCheckout.session_id}",
                      headers=_hdr(TestStripeCheckout._tok))
        r2 = http.get(f"{BASE_URL}/api/payments/status/{TestStripeCheckout.session_id}",
                      headers=_hdr(TestStripeCheckout._tok))
        assert r1.json() == r2.json()


# ---------- Merchant batches ----------
class TestBatches:
    batch_id = None
    course_id = None

    def test_create_batch(self, http, merchant):
        # Reuse a merchant-owned course from prior class if available, else create one
        courses = http.get(f"{BASE_URL}/api/merchant/courses", headers=_hdr(merchant["token"])).json()
        if not courses:
            r = http.post(f"{BASE_URL}/api/merchant/courses", headers=_hdr(merchant["token"]),
                          json={"title": "TEST_BatchCourse", "description": "x", "category": "Design",
                                "fees": 500, "duration": "2 weeks", "curriculum": []})
            assert r.status_code == 200
            TestBatches.course_id = r.json()["id"]
        else:
            TestBatches.course_id = courses[0]["id"]

        r = http.post(f"{BASE_URL}/api/merchant/batches", headers=_hdr(merchant["token"]),
                      json={"course_id": TestBatches.course_id, "schedule": "Mon/Wed 7pm",
                            "capacity": 20, "coordinator": "Alice",
                            "start_date": "2026-02-01", "end_date": "2026-04-01",
                            "meet_link": "https://meet.google.com/xyz-test"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["meet_link"] == "https://meet.google.com/xyz-test"
        assert data["capacity"] == 20
        assert data["status"] == "active"
        TestBatches.batch_id = data["id"]

    def test_attendance_get_returns_students(self, http, merchant):
        r = http.get(f"{BASE_URL}/api/merchant/batches/{TestBatches.batch_id}/attendance",
                     headers=_hdr(merchant["token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "batch" in data and "students" in data

    def test_attendance_mark(self, http, merchant, student):
        r = http.post(f"{BASE_URL}/api/merchant/batches/{TestBatches.batch_id}/attendance",
                      headers=_hdr(merchant["token"]),
                      json={"student_id": student["user"]["id"], "present": True})
        assert r.status_code == 200
        assert r.json()["present"] is True


# ---------- Ratings ----------
class TestRatings:
    def test_non_enrolled_rating_forbidden(self, http, student2):
        r = http.post(f"{BASE_URL}/api/reviews", headers=_hdr(student2["token"]),
                      json={"rating": 5, "text": "no way", "target_type": "courses",
                            "target_id": "course-ai"})
        assert r.status_code == 403

    def test_enrolled_student_can_rate(self, http):
        # Free course auto-enrolls -> can rate
        tok, u = _auth(http, "9" + uuid.uuid4().hex[:9], "student")
        enr = http.post(f"{BASE_URL}/api/enrollments", headers=_hdr(tok),
                        json={"course_id": "course-marketing"})
        assert enr.status_code == 200 and enr.json()["status"] == "active"

        r = http.post(f"{BASE_URL}/api/reviews", headers=_hdr(tok),
                      json={"rating": 4, "text": "TEST_review great course",
                            "target_type": "courses", "target_id": "course-marketing"})
        assert r.status_code == 200, r.text
        assert r.json()["rating"] == 4

        # Verify recalc
        detail = http.get(f"{BASE_URL}/api/courses/course-marketing").json()
        assert detail["course"]["reviews_count"] >= 1


# ---------- Refunds ----------
class TestRefunds:
    refund_id = None
    admin_tok = None

    def test_refund_rejected_for_unpaid(self, http, student):
        # student has pending_payment enrollment for course-product from cart test
        enrs = http.get(f"{BASE_URL}/api/me/enrollments", headers=_hdr(student["token"])).json()
        pending = [e for e in enrs if e.get("payment_status") == "pending"]
        if pending:
            r = http.post(f"{BASE_URL}/api/refunds", headers=_hdr(student["token"]),
                          json={"enrollment_id": pending[0]["id"], "reason": "TEST"})
            assert r.status_code == 400

    def test_refund_created_for_paid(self, http):
        # Free enrollment is 'paid' with amount 0 but marked payment_status='paid'
        tok, u = _auth(http, "9" + uuid.uuid4().hex[:9], "student")
        enr = http.post(f"{BASE_URL}/api/enrollments", headers=_hdr(tok),
                        json={"course_id": "course-marketing"}).json()
        assert enr["payment_status"] == "paid"

        r = http.post(f"{BASE_URL}/api/refunds", headers=_hdr(tok),
                      json={"enrollment_id": enr["id"], "reason": "TEST_refund reason"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        TestRefunds.refund_id = r.json()["id"]
        TestRefunds._enrollment_id = enr["id"]
        TestRefunds._tok = tok

    def test_admin_lists_refunds(self, http, admin):
        r = http.get(f"{BASE_URL}/api/admin/refunds", headers=_hdr(admin["token"]))
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert TestRefunds.refund_id in ids

    def test_admin_approves_refund(self, http, admin):
        r = http.post(f"{BASE_URL}/api/admin/refunds/{TestRefunds.refund_id}/action",
                      headers=_hdr(admin["token"]), params={"status": "approved"})
        assert r.status_code == 200 and r.json()["status"] == "approved"

        # verify enrollment marked refunded
        enrs = http.get(f"{BASE_URL}/api/me/enrollments", headers=_hdr(TestRefunds._tok)).json()
        target = next(e for e in enrs if e["id"] == TestRefunds._enrollment_id)
        assert target["status"] == "refunded"
        assert target["payment_status"] == "refunded"


# ---------- Admin audit logs ----------
class TestAuditLogs:
    def test_audit_logs_present(self, http, admin):
        r = http.get(f"{BASE_URL}/api/admin/audit-logs", headers=_hdr(admin["token"]))
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 1
        # Expect entries from our approvals above
        actions = " ".join([str(x.get("action", "")) for x in rows])
        assert "Coupon" in actions or "Course" in actions or "Refund" in actions
