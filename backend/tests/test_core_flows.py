"""Regression coverage for discovery, authentication, lists, enrollment, admin, and merchant APIs."""
import os
import uuid

import pytest
import requests


BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")).rstrip("/")


@pytest.fixture
def client():
    return requests.Session()


def token(client, mobile, role="student"):
    response = client.post(f"{BASE_URL}/api/auth/verify-otp", json={"mobile": mobile, "otp": "123456", "role": role})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_home_and_course_search(client):
    home = client.get(f"{BASE_URL}/api/home")
    assert home.status_code == 200 and home.json()["courses"] and home.json()["institutes"]
    search = client.get(f"{BASE_URL}/api/courses", params={"q": "python"})
    assert search.status_code == 200 and any("Python" in row["title"] for row in search.json())


def test_student_lists_and_enrollment_payment_states(client):
    mobile = "9" + uuid.uuid4().hex[:9]
    auth = client.post(f"{BASE_URL}/api/auth/verify-otp", json={"mobile": mobile, "otp": "123456", "role": "student"})
    assert auth.status_code == 200
    bearer = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    lists = client.post(f"{BASE_URL}/api/me/cart", headers=bearer, json={"course_id": "course-product"})
    assert lists.status_code == 200 and "course-product" in lists.json()["cart"]
    enrollment = client.post(f"{BASE_URL}/api/enrollments", headers=bearer, json={"course_id": "course-product"})
    assert enrollment.status_code == 200 and enrollment.json()["status"] == "pending_payment"
    paid = client.post(f"{BASE_URL}/api/payments/confirm", headers=bearer, json={"enrollment_id": enrollment.json()["id"], "success": True})
    assert paid.status_code == 200 and paid.json()["status"] == "active"


def test_admin_and_merchant_protected_dashboards(client):
    admin_login = client.post(f"{BASE_URL}/api/auth/admin-login", json={"email": "admin@corzaar.com", "password": "Admin@123"})
    assert admin_login.status_code == 200 and admin_login.json()["requires_otp"] is True
    admin = client.post(f"{BASE_URL}/api/auth/admin-verify", json={"email": "admin@corzaar.com", "otp": "123456"})
    assert admin.status_code == 200
    dashboard = client.get(f"{BASE_URL}/api/admin/dashboard", headers={"Authorization": f"Bearer {admin.json()['access_token']}"})
    assert dashboard.status_code == 200 and "total_students" in dashboard.json()
    merchant_token = token(client, "8" + uuid.uuid4().hex[:9], "merchant")
    merchant = client.get(f"{BASE_URL}/api/merchant/dashboard", headers={"Authorization": f"Bearer {merchant_token}"})
    assert merchant.status_code == 200 and "active_courses" in merchant.json()