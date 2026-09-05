import urllib.request
import json
import sys

base_url = "http://127.0.0.1:8000"

print("--- DRISHTI Live Authentication Verification ---")

# 1. Test Invalid Login
req_invalid = urllib.request.Request(
    f"{base_url}/auth/login",
    data=json.dumps({"email": "officer@drishti.gov.in", "password": "WrongPassword"}).encode(),
    headers={"Content-Type": "application/json"}
)
try:
    urllib.request.urlopen(req_invalid)
    print("FAILED: Expected 401 on invalid password")
    sys.exit(1)
except urllib.error.HTTPError as e:
    print(f"1. Invalid Login Rejected: HTTP {e.code} (Correct)")
    assert e.code == 401

# 2. Test Valid Login
req_valid = urllib.request.Request(
    f"{base_url}/auth/login",
    data=json.dumps({"email": "officer@drishti.gov.in", "password": "AuthorityOfficer2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req_valid) as resp:
    print(f"2. Valid Officer Login Succeeded: HTTP {resp.status}")
    login_data = json.loads(resp.read().decode())
    token = login_data["access_token"]
    assert token is not None
    user_role = login_data["user"]["role"]
    assert user_role == "AUTHORITY_OFFICER"
    print(f"   Token generated: {token[:25]}... (Role: {user_role})")

# 3. Test Unauthorized Access
req_unauth = urllib.request.Request(f"{base_url}/auth/me")
try:
    urllib.request.urlopen(req_unauth)
    print("FAILED: Expected 401 on unauthorized /auth/me")
    sys.exit(1)
except urllib.error.HTTPError as e:
    print(f"3. Unauthorized Access to /auth/me Rejected: HTTP {e.code} (Correct)")
    assert e.code == 401

# 4. Test Authorized /auth/me
req_me = urllib.request.Request(
    f"{base_url}/auth/me",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req_me) as resp:
    print(f"4. Authorized /auth/me Succeeded: HTTP {resp.status}")
    me_data = json.loads(resp.read().decode())
    officer_name = me_data["user"]["full_name"]
    badge_id = me_data["user"]["badge_id"]
    assert badge_id == "FSO-DL-CENTRAL-012"
    print(f"   Officer Identity: {officer_name} | Badge: {badge_id}")

# 5. Test Protected Business Route
req_triage = urllib.request.Request(
    f"{base_url}/api/v1/cases/triage",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req_triage) as resp:
    print(f"5. Protected /api/v1/cases/triage Route Accessible: HTTP {resp.status}")

# 6. Test Logout
req_logout = urllib.request.Request(
    f"{base_url}/auth/logout",
    data=b"{}",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
)
with urllib.request.urlopen(req_logout) as resp:
    print(f"6. Officer Logout Succeeded: HTTP {resp.status}")
    logout_data = json.loads(resp.read().decode())
    assert logout_data["status"] == "success"
    print(f"   Response: {logout_data['message']}")

print("\n>>> ALL 6 LIVE AUTHENTICATION TESTS PASSED SUCCESSFULLY! <<<")
