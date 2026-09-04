#!/usr/bin/env python3
"""
CORZAAR IMS Backend Test Suite
Tests all backend APIs including new certificate management features
"""
import requests
import json
import re
import time
from typing import Dict, Any, Optional

# Base URL from frontend .env
BASE_URL = "https://corzaar-staging.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@corzaar.com"
ADMIN_PASSWORD = "Admin@123"
ADMIN_OTP = "123456"
TEST_OTP = "123456"

# Test mobile numbers
MERCHANT_MOBILE = "9999900001"
STUDENT_MOBILE = "9999900002"

# Global tokens
admin_token = None
merchant_token = None
student_token = None

# Test data storage
test_data = {
    "template_id": None,
    "course_id": None,
    "enrollment_id": None,
    "certificate_id": None,
    "cert_internal_id": None,
}

def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"    {details}")
    if not passed:
        print()

def make_request(method: str, endpoint: str, token: Optional[str] = None, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> tuple:
    """Make HTTP request and return (success, response_json, status_code)"""
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=10)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json_data, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=10)
        else:
            return False, {}, 0
        
        try:
            data = resp.json()
        except:
            data = {"text": resp.text}
        
        return resp.status_code < 400, data, resp.status_code
    except Exception as e:
        return False, {"error": str(e)}, 0

def test_health():
    """Test 1: Health check"""
    success, data, status = make_request("GET", "/")
    log_test("Health check GET /api/", success and status == 200, f"Status: {status}")
    return success

def test_home_discovery():
    """Test 2: Home discovery data"""
    success, data, status = make_request("GET", "/home")
    
    if not success:
        log_test("GET /api/home", False, f"Request failed: {status}")
        return False
    
    # Check required keys
    has_discovery_cats = "discovery_categories" in data
    has_popular_locs = "popular_locations" in data
    has_duration_buckets = "duration_buckets" in data
    
    # Validate discovery_categories structure
    valid_cats = False
    if has_discovery_cats and isinstance(data["discovery_categories"], list) and len(data["discovery_categories"]) > 0:
        first_cat = data["discovery_categories"][0]
        valid_cats = "key" in first_cat and "icon" in first_cat
    
    # Validate popular_locations
    valid_locs = has_popular_locs and isinstance(data["popular_locations"], list)
    
    # Validate duration_buckets (should have 5 items)
    valid_buckets = False
    if has_duration_buckets and isinstance(data["duration_buckets"], list):
        valid_buckets = len(data["duration_buckets"]) == 5
        if valid_buckets:
            first_bucket = data["duration_buckets"][0]
            valid_buckets = "key" in first_bucket and "label" in first_bucket
    
    all_valid = valid_cats and valid_locs and valid_buckets
    details = f"discovery_categories: {valid_cats}, popular_locations: {valid_locs}, duration_buckets(5): {valid_buckets}"
    log_test("GET /api/home discovery data", all_valid, details)
    return all_valid

def test_courses_filters():
    """Test 3: Enhanced course filters"""
    tests_passed = []
    
    # Test 3a: Category filter
    success, data, status = make_request("GET", "/courses", params={"category": "Technology"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?category=Technology", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3b: Free only filter
    success, data, status = make_request("GET", "/courses", params={"free_only": "true"})
    passed = success and isinstance(data, list)
    if passed and len(data) > 0:
        # Check if any course has fees <= 0
        has_free = any(c.get("fees", 999) <= 0 for c in data)
        passed = has_free
    tests_passed.append(passed)
    log_test("GET /api/courses?free_only=true", passed, f"Returned {len(data) if success else 0} courses")
    
    # Test 3c: Price range filter
    success, data, status = make_request("GET", "/courses", params={"price_min": "15000", "price_max": "20000"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?price_min=15000&price_max=20000", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3d: Min rating filter
    success, data, status = make_request("GET", "/courses", params={"min_rating": "4.8"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?min_rating=4.8", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3e: Duration filter (1-3 months)
    success, data, status = make_request("GET", "/courses", params={"duration": "1_3m"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?duration=1_3m", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3f: Duration filter (under 1 month)
    success, data, status = make_request("GET", "/courses", params={"duration": "under_1m"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?duration=under_1m", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3g: Mode filter
    success, data, status = make_request("GET", "/courses", params={"mode": "Hybrid"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?mode=Hybrid", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3h: Location filter
    success, data, status = make_request("GET", "/courses", params={"location": "Mumbai"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?location=Mumbai", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3i: Sort by price ascending
    success, data, status = make_request("GET", "/courses", params={"sort": "price_asc"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?sort=price_asc", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3j: Sort by price descending
    success, data, status = make_request("GET", "/courses", params={"sort": "price_desc"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?sort=price_desc", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3k: Sort by newest
    success, data, status = make_request("GET", "/courses", params={"sort": "newest"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?sort=newest", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3l: Sort by students
    success, data, status = make_request("GET", "/courses", params={"sort": "students"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?sort=students", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3m: Has certificate filter
    success, data, status = make_request("GET", "/courses", params={"has_certificate": "true"})
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses?has_certificate=true", passed, f"Returned {len(data) if passed else 0} courses")
    
    # Test 3n: Combined filters
    success, data, status = make_request("GET", "/courses", params={
        "category": "Technology",
        "min_rating": "4.0",
        "sort": "price_asc"
    })
    passed = success and isinstance(data, list)
    tests_passed.append(passed)
    log_test("GET /api/courses (combined filters)", passed, f"Returned {len(data) if passed else 0} courses")
    
    return all(tests_passed)

def auth_merchant():
    """Authenticate as merchant"""
    global merchant_token
    
    # Send OTP
    success, data, status = make_request("POST", "/auth/send-otp", json_data={
        "mobile": MERCHANT_MOBILE,
        "role": "merchant"
    })
    
    if not success:
        log_test("Merchant auth - send OTP", False, f"Status: {status}")
        return False
    
    # Verify OTP
    success, data, status = make_request("POST", "/auth/verify-otp", json_data={
        "mobile": MERCHANT_MOBILE,
        "otp": TEST_OTP,
        "role": "merchant"
    })
    
    if success and "access_token" in data:
        merchant_token = data["access_token"]
        log_test("Merchant auth - verify OTP", True, "Token obtained")
        return True
    else:
        log_test("Merchant auth - verify OTP", False, f"Status: {status}")
        return False

def test_certificate_templates():
    """Test 4: Certificate templates CRUD"""
    global merchant_token, test_data
    
    if not merchant_token:
        if not auth_merchant():
            log_test("Certificate templates CRUD", False, "Merchant auth failed")
            return False
    
    tests_passed = []
    
    # Test 4a: Create template with valid style
    success, data, status = make_request("POST", "/merchant/certificate-templates", merchant_token, json_data={
        "name": "Test Template 1",
        "style": "classic",
        "accent_color": "#1E3A5F",
        "signatory": "Program Lead"
    })
    
    if success and "id" in data:
        test_data["template_id"] = data["id"]
        tests_passed.append(True)
        log_test("POST /api/merchant/certificate-templates (valid)", True, f"Template ID: {data['id']}")
    else:
        tests_passed.append(False)
        log_test("POST /api/merchant/certificate-templates (valid)", False, f"Status: {status}")
    
    # Test 4b: Create template with invalid style (should fail with 400)
    success, data, status = make_request("POST", "/merchant/certificate-templates", merchant_token, json_data={
        "name": "Bad Template",
        "style": "weird",
        "accent_color": "#FF0000",
        "signatory": "Test"
    })
    
    passed = not success and status == 400
    tests_passed.append(passed)
    log_test("POST /api/merchant/certificate-templates (invalid style)", passed, f"Status: {status} (expected 400)")
    
    # Test 4c: Get templates
    success, data, status = make_request("GET", "/merchant/certificate-templates", merchant_token)
    passed = success and isinstance(data, list) and len(data) > 0
    if passed:
        # Check if our template is in the list
        found = any(t.get("id") == test_data["template_id"] for t in data)
        passed = found
    tests_passed.append(passed)
    log_test("GET /api/merchant/certificate-templates", passed, f"Found {len(data) if success else 0} templates")
    
    # Test 4d: Delete template (will do this later after testing course config)
    
    return all(tests_passed)

def test_course_certificate_config():
    """Test 5: Per-course certificate configuration"""
    global merchant_token, test_data
    
    if not merchant_token:
        if not auth_merchant():
            log_test("Course certificate config", False, "Merchant auth failed")
            return False
    
    tests_passed = []
    
    # First, create a course
    success, data, status = make_request("POST", "/merchant/courses", merchant_token, json_data={
        "title": "Manual Cert Course",
        "description": "Test course for manual certificate issuance",
        "category": "Technology",
        "fees": 0,
        "duration": "4 weeks",
        "curriculum": ["Intro", "Practice", "Wrap"]
    })
    
    if success and "id" in data:
        test_data["course_id"] = data["id"]
        log_test("Create test course", True, f"Course ID: {data['id']}")
    else:
        log_test("Create test course", False, f"Status: {status}")
        return False
    
    # Publish the course as admin (need admin auth first)
    if not auth_admin():
        log_test("Course certificate config", False, "Admin auth failed")
        return False
    
    success, data, status = make_request("POST", f"/admin/courses/{test_data['course_id']}/status", admin_token, params={"status": "published"})
    if success:
        log_test("Publish test course", True, "Course published")
    else:
        log_test("Publish test course", False, f"Status: {status}")
    
    # Re-create template as merchant (needed for template_id)
    if not test_data["template_id"]:
        success, data, status = make_request("POST", "/merchant/certificate-templates", merchant_token, json_data={
            "name": "Test Template 2",
            "style": "modern",
            "accent_color": "#0EA5A0",
            "signatory": "Director"
        })
        if success and "id" in data:
            test_data["template_id"] = data["id"]
    
    # Test 5a: Set certificate config with manual issue
    success, data, status = make_request("PUT", f"/merchant/courses/{test_data['course_id']}/certificate", merchant_token, json_data={
        "enabled": True,
        "template_id": test_data["template_id"],
        "certificate_name": "Data Cert",
        "completion_percent": 100,
        "issue_method": "manual"
    })
    
    passed = success and status == 200
    tests_passed.append(passed)
    log_test("PUT /api/merchant/courses/{id}/certificate (manual)", passed, f"Status: {status}")
    
    # Test 5b: Invalid issue_method (should fail with 400)
    success, data, status = make_request("PUT", f"/merchant/courses/{test_data['course_id']}/certificate", merchant_token, json_data={
        "enabled": True,
        "template_id": test_data["template_id"],
        "certificate_name": "Test Cert",
        "completion_percent": 100,
        "issue_method": "weird"
    })
    
    passed = not success and status == 400
    tests_passed.append(passed)
    log_test("PUT /api/merchant/courses/{id}/certificate (invalid method)", passed, f"Status: {status} (expected 400)")
    
    # Test 5c: Invalid completion_percent (below 10, should fail with 422)
    success, data, status = make_request("PUT", f"/merchant/courses/{test_data['course_id']}/certificate", merchant_token, json_data={
        "enabled": True,
        "template_id": test_data["template_id"],
        "certificate_name": "Test Cert",
        "completion_percent": 5,
        "issue_method": "manual"
    })
    
    passed = not success and status == 422
    tests_passed.append(passed)
    log_test("PUT /api/merchant/courses/{id}/certificate (invalid percent)", passed, f"Status: {status} (expected 422)")
    
    return all(tests_passed)

def auth_admin():
    """Authenticate as admin"""
    global admin_token
    
    # Admin login
    success, data, status = make_request("POST", "/auth/admin-login", json_data={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if not success:
        log_test("Admin auth - login", False, f"Status: {status}")
        return False
    
    # Admin verify OTP
    success, data, status = make_request("POST", "/auth/admin-verify", json_data={
        "email": ADMIN_EMAIL,
        "otp": ADMIN_OTP
    })
    
    if success and "access_token" in data:
        admin_token = data["access_token"]
        log_test("Admin auth - verify", True, "Token obtained")
        return True
    else:
        log_test("Admin auth - verify", False, f"Status: {status}")
        return False

def auth_student():
    """Authenticate as student"""
    global student_token
    
    # Send OTP
    success, data, status = make_request("POST", "/auth/send-otp", json_data={
        "mobile": STUDENT_MOBILE,
        "role": "student"
    })
    
    if not success:
        log_test("Student auth - send OTP", False, f"Status: {status}")
        return False
    
    # Verify OTP
    success, data, status = make_request("POST", "/auth/verify-otp", json_data={
        "mobile": STUDENT_MOBILE,
        "otp": TEST_OTP,
        "role": "student"
    })
    
    if success and "access_token" in data:
        student_token = data["access_token"]
        log_test("Student auth - verify OTP", True, "Token obtained")
        return True
    else:
        log_test("Student auth - verify OTP", False, f"Status: {status}")
        return False

def test_certificate_lifecycle_manual():
    """Test 6: Certificate lifecycle with manual issuance"""
    global student_token, merchant_token, test_data
    
    if not student_token:
        if not auth_student():
            log_test("Certificate lifecycle (manual)", False, "Student auth failed")
            return False
    
    tests_passed = []
    
    # Test 6a: Enroll in the manual-cert course
    success, data, status = make_request("POST", "/enrollments", student_token, json_data={
        "course_id": test_data["course_id"]
    })
    
    if success and "id" in data:
        test_data["enrollment_id"] = data["id"]
        tests_passed.append(True)
        log_test("POST /api/enrollments (manual cert course)", True, f"Enrollment ID: {data['id']}")
    else:
        tests_passed.append(False)
        log_test("POST /api/enrollments (manual cert course)", False, f"Status: {status}")
        return False
    
    # Test 6b: Mark 100% progress
    success, data, status = make_request("POST", f"/me/enrollments/{test_data['enrollment_id']}/progress", student_token, json_data={
        "completed": ["Intro", "Practice", "Wrap"]
    })
    
    if success:
        progress = data.get("progress", 0)
        has_cert_id = "certificate_id" in data and data["certificate_id"] is not None
        
        # For manual issue, certificate_id should NOT be set yet
        passed = progress == 100 and not has_cert_id
        tests_passed.append(passed)
        log_test("POST /api/me/enrollments/{id}/progress (100%)", passed, f"Progress: {progress}%, certificate_id: {has_cert_id} (should be False for manual)")
    else:
        tests_passed.append(False)
        log_test("POST /api/me/enrollments/{id}/progress (100%)", False, f"Status: {status}")
        return False
    
    # Test 6c: Check merchant certificates for pending approval
    time.sleep(1)  # Give it a moment to process
    success, data, status = make_request("GET", "/merchant/certificates", merchant_token)
    
    if success and "certificates" in data:
        certs = data["certificates"]
        # Find certificate with status=pending_approval
        pending = [c for c in certs if c.get("status") == "pending_approval"]
        
        if pending:
            cert = pending[0]
            test_data["cert_internal_id"] = cert["id"]
            test_data["certificate_id"] = cert["certificate_id"]
            
            # Validate certificate ID format: CORZAAR-[A-Z0-9]{1,4}-[A-Z0-9]{1,4}-[A-F0-9]{8}
            cert_id_pattern = r"^CORZAAR-[A-Z0-9]{1,4}-[A-Z0-9]{1,4}-[A-F0-9]{8}$"
            valid_format = re.match(cert_id_pattern, cert["certificate_id"]) is not None
            
            passed = valid_format
            tests_passed.append(passed)
            log_test("GET /api/merchant/certificates (pending)", passed, f"Found pending cert: {cert['certificate_id']}, valid format: {valid_format}")
        else:
            tests_passed.append(False)
            log_test("GET /api/merchant/certificates (pending)", False, "No pending certificates found")
            return False
    else:
        tests_passed.append(False)
        log_test("GET /api/merchant/certificates (pending)", False, f"Status: {status}")
        return False
    
    # Test 6d: Approve certificate
    success, data, status = make_request("POST", f"/merchant/certificates/{test_data['cert_internal_id']}/approve", merchant_token)
    
    passed = success and data.get("status") == "issued"
    tests_passed.append(passed)
    log_test("POST /api/merchant/certificates/{id}/approve", passed, f"Status: {data.get('status') if success else status}")
    
    # Test 6e: Verify enrollment now has certificate_id
    time.sleep(1)
    success, data, status = make_request("GET", "/me/enrollments", student_token)
    
    if success and isinstance(data, list):
        enrollment = next((e for e in data if e["id"] == test_data["enrollment_id"]), None)
        if enrollment:
            has_cert_id = "certificate_id" in enrollment and enrollment["certificate_id"] is not None
            passed = has_cert_id
            tests_passed.append(passed)
            log_test("GET /api/me/enrollments (cert_id set)", passed, f"certificate_id: {enrollment.get('certificate_id')}")
        else:
            tests_passed.append(False)
            log_test("GET /api/me/enrollments (cert_id set)", False, "Enrollment not found")
    else:
        tests_passed.append(False)
        log_test("GET /api/me/enrollments (cert_id set)", False, f"Status: {status}")
    
    return all(tests_passed)

def test_certificate_lifecycle_automatic():
    """Test 7: Certificate lifecycle with automatic issuance"""
    global student_token, merchant_token, test_data
    
    if not student_token or not merchant_token:
        log_test("Certificate lifecycle (automatic)", False, "Auth failed")
        return False
    
    tests_passed = []
    
    # Create another course with automatic issuance
    success, data, status = make_request("POST", "/merchant/courses", merchant_token, json_data={
        "title": "Auto Cert Course",
        "description": "Test course for automatic certificate issuance",
        "category": "Technology",
        "fees": 0,
        "duration": "6 weeks",
        "curriculum": ["Module 1", "Module 2", "Module 3"]
    })
    
    if not success or "id" not in data:
        log_test("Certificate lifecycle (automatic)", False, "Failed to create auto course")
        return False
    
    auto_course_id = data["id"]
    
    # Publish the course
    success, data, status = make_request("POST", f"/admin/courses/{auto_course_id}/status", admin_token, params={"status": "published"})
    
    # Set certificate config to automatic
    success, data, status = make_request("PUT", f"/merchant/courses/{auto_course_id}/certificate", merchant_token, json_data={
        "enabled": True,
        "template_id": test_data["template_id"],
        "certificate_name": "Auto Certificate",
        "completion_percent": 100,
        "issue_method": "automatic"
    })
    
    if not success:
        log_test("Certificate lifecycle (automatic)", False, "Failed to set auto config")
        return False
    
    # Enroll as student
    success, data, status = make_request("POST", "/enrollments", student_token, json_data={
        "course_id": auto_course_id
    })
    
    if not success or "id" not in data:
        log_test("Certificate lifecycle (automatic)", False, "Failed to enroll")
        return False
    
    auto_enrollment_id = data["id"]
    
    # Mark 100% progress
    success, data, status = make_request("POST", f"/me/enrollments/{auto_enrollment_id}/progress", student_token, json_data={
        "completed": ["Module 1", "Module 2", "Module 3"]
    })
    
    if success:
        progress = data.get("progress", 0)
        has_cert_id = "certificate_id" in data and data["certificate_id"] is not None
        
        # For automatic issue, certificate_id SHOULD be set immediately
        passed = progress == 100 and has_cert_id
        tests_passed.append(passed)
        log_test("Certificate lifecycle (automatic)", passed, f"Progress: {progress}%, certificate_id set: {has_cert_id} (should be True for automatic)")
    else:
        tests_passed.append(False)
        log_test("Certificate lifecycle (automatic)", False, f"Status: {status}")
    
    return all(tests_passed)

def test_admin_revoke():
    """Test 8: Admin certificate revoke"""
    global admin_token, student_token, test_data
    
    if not admin_token or not test_data["cert_internal_id"]:
        log_test("Admin revoke certificate", False, "Missing auth or cert ID")
        return False
    
    tests_passed = []
    
    # Test 8a: Revoke certificate
    success, data, status = make_request("POST", f"/admin/certificates/{test_data['cert_internal_id']}/revoke", admin_token)
    
    passed = success and data.get("status") == "revoked"
    tests_passed.append(passed)
    log_test("POST /api/admin/certificates/{id}/revoke", passed, f"Status: {data.get('status') if success else status}")
    
    # Test 8b: Verify enrollment.certificate_id is unset
    time.sleep(1)
    success, data, status = make_request("GET", "/me/enrollments", student_token)
    
    if success and isinstance(data, list):
        enrollment = next((e for e in data if e["id"] == test_data["enrollment_id"]), None)
        if enrollment:
            has_cert_id = "certificate_id" in enrollment and enrollment["certificate_id"] is not None
            passed = not has_cert_id
            tests_passed.append(passed)
            log_test("Enrollment certificate_id unset after revoke", passed, f"certificate_id present: {has_cert_id} (should be False)")
        else:
            tests_passed.append(False)
            log_test("Enrollment certificate_id unset after revoke", False, "Enrollment not found")
    else:
        tests_passed.append(False)
        log_test("Enrollment certificate_id unset after revoke", False, f"Status: {status}")
    
    return all(tests_passed)

def test_public_verification():
    """Test 9: Public certificate verification (no auth)"""
    global test_data
    
    if not test_data["certificate_id"]:
        log_test("Public certificate verification", False, "No certificate ID available")
        return False
    
    tests_passed = []
    
    # Test 9a: Verify issued certificate (now revoked, so should be valid=false)
    success, data, status = make_request("GET", f"/certificates/verify/{test_data['certificate_id']}")
    
    # Since we revoked it, valid should be False
    passed = success and data.get("valid") == False and data.get("status") == "revoked"
    tests_passed.append(passed)
    log_test("GET /api/certificates/verify/{cert_id} (revoked)", passed, f"valid: {data.get('valid')}, status: {data.get('status')}")
    
    # Test 9b: Verify HTML view
    url = f"{BASE_URL}/certificates/verify/{test_data['certificate_id']}/view"
    try:
        resp = requests.get(url, timeout=10)
        passed = resp.status_code == 200 and "html" in resp.text.lower()
        tests_passed.append(passed)
        log_test("GET /api/certificates/verify/{cert_id}/view (HTML)", passed, f"Status: {resp.status_code}")
    except Exception as e:
        tests_passed.append(False)
        log_test("GET /api/certificates/verify/{cert_id}/view (HTML)", False, str(e))
    
    # Test 9c: Verify unknown certificate
    success, data, status = make_request("GET", "/certificates/verify/UNKNOWN-ID")
    
    passed = success and data.get("valid") == False and data.get("status") == "invalid"
    tests_passed.append(passed)
    log_test("GET /api/certificates/verify/UNKNOWN-ID", passed, f"valid: {data.get('valid')}, status: {data.get('status')}")
    
    return all(tests_passed)

def test_regression():
    """Test 10: Regression tests for existing flows"""
    tests_passed = []
    
    # Test 10a: Default courses listing
    success, data, status = make_request("GET", "/courses")
    passed = success and isinstance(data, list) and len(data) >= 4
    tests_passed.append(passed)
    log_test("GET /api/courses (default)", passed, f"Returned {len(data) if success else 0} courses (expected >= 4)")
    
    # Test 10b: /me endpoint
    if student_token:
        success, data, status = make_request("GET", "/me", student_token)
        passed = success and "id" in data
        tests_passed.append(passed)
        log_test("GET /api/me", passed, f"Status: {status}")
    
    # Test 10c: /me/lists
    if student_token:
        success, data, status = make_request("GET", "/me/lists", student_token)
        passed = success and "cart" in data and "favorites" in data
        tests_passed.append(passed)
        log_test("GET /api/me/lists", passed, f"Status: {status}")
    
    # Test 10d: /me/referrals
    if student_token:
        success, data, status = make_request("GET", "/me/referrals", student_token)
        passed = success and "code" in data
        tests_passed.append(passed)
        log_test("GET /api/me/referrals", passed, f"Referral code: {data.get('code') if success else 'N/A'}")
    
    # Test 10e: /me/notifications
    if student_token:
        success, data, status = make_request("GET", "/me/notifications", student_token)
        passed = success and isinstance(data, list)
        tests_passed.append(passed)
        log_test("GET /api/me/notifications", passed, f"Returned {len(data) if success else 0} notifications")
    
    # Test 10f: Coupon validation
    success, data, status = make_request("POST", "/coupons/validate", json_data={
        "code": "WELCOME10",
        "course_id": test_data.get("course_id", "test-id")
    })
    # This might fail if coupon doesn't exist, but endpoint should respond
    passed = status in [200, 404]
    tests_passed.append(passed)
    log_test("POST /api/coupons/validate", passed, f"Status: {status}")
    
    return all(tests_passed)

def test_delete_template():
    """Test 11: Delete certificate template"""
    global merchant_token, test_data
    
    if not merchant_token or not test_data["template_id"]:
        log_test("DELETE certificate template", False, "Missing auth or template ID")
        return False
    
    success, data, status = make_request("DELETE", f"/merchant/certificate-templates/{test_data['template_id']}", merchant_token)
    
    passed = success and status == 200
    log_test("DELETE /api/merchant/certificate-templates/{id}", passed, f"Status: {status}")
    return passed

def main():
    """Run all tests"""
    print("=" * 80)
    print("CORZAAR IMS Backend Test Suite")
    print("=" * 80)
    print()
    
    # Run tests in order
    print("--- Basic Tests ---")
    test_health()
    test_home_discovery()
    print()
    
    print("--- Course Filter Tests ---")
    test_courses_filters()
    print()
    
    print("--- Certificate Template Tests ---")
    test_certificate_templates()
    print()
    
    print("--- Course Certificate Config Tests ---")
    test_course_certificate_config()
    print()
    
    print("--- Certificate Lifecycle Tests (Manual) ---")
    test_certificate_lifecycle_manual()
    print()
    
    print("--- Certificate Lifecycle Tests (Automatic) ---")
    test_certificate_lifecycle_automatic()
    print()
    
    print("--- Admin Revoke Tests ---")
    test_admin_revoke()
    print()
    
    print("--- Public Verification Tests ---")
    test_public_verification()
    print()
    
    print("--- Regression Tests ---")
    test_regression()
    print()
    
    print("--- Cleanup ---")
    test_delete_template()
    print()
    
    print("=" * 80)
    print("Test suite completed")
    print("=" * 80)

if __name__ == "__main__":
    main()
