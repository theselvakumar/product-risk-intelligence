import urllib.request
import json

base_url = "http://127.0.0.1:8000"

# 1. Login to get token
req_login = urllib.request.Request(
    f"{base_url}/auth/login",
    data=json.dumps({"email": "officer@drishti.gov.in", "password": "AuthorityOfficer2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req_login) as resp:
    token = json.loads(resp.read().decode())["access_token"]

headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

# 2. Test metrics
req_metrics = urllib.request.Request(f"{base_url}/api/v1/cases/metrics", headers=headers)
with urllib.request.urlopen(req_metrics) as resp:
    metrics = json.loads(resp.read().decode())
    print("Metrics Live API Result:", json.dumps(metrics, indent=2))

# 3. Test recent cases
req_recent = urllib.request.Request(f"{base_url}/api/v1/cases/recent?limit=5", headers=headers)
with urllib.request.urlopen(req_recent) as resp:
    recent = json.loads(resp.read().decode())
    print(f"Recent Cases Live API: Retrieved {len(recent)} items")
    for c in recent[:3]:
        print(f"  - {c['case_number']}: {c['product_name']} ({c['risk_level']}, Risk: {c['risk_score']})")

print("\n>>> LIVE DASHBOARD AND CASES APIs WORKING PERFECTLY! <<<")
