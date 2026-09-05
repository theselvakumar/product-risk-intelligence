# DRISHTI Regulatory Platform — Security, Access Control & Auditability Architecture

**Document Version:** 1.0.0  
**Effective Date:** September 2026  
**Classification:** Official Regulatory Standard — FSSAI Digital Surveillance  
**Applicability:** DRISHTI Core Backend, Frontend Portals, and Ingestion Gateways

---

## 1. Executive Summary & Security Philosophy

The **DRISHTI** (Digital Regulatory Intelligence & Surveillance for Health Compliance Tracking) system is an authority-facing regulatory intelligence platform. Because the evidence collected and decisions recorded within DRISHTI form the statutory foundation for notices under Section 32 of the Food Safety and Standards Act (FSSA 2006), the architecture is founded upon four non-negotiable security principles:

1. **Zero-Trust Statutory Integrity**: No action that alters regulatory state or triggers enforcement proceedings may occur without cryptographic authentication and immutable attribution to an authorized officer.
2. **Strict Separation of AI from Enforcement**: Artificial intelligence and machine learning pipelines provide advisory risk scoring and evidence discovery; they are cryptographically and architecturally prevented from automatically dismissing cases, issuing penalties, or closing cases.
3. **Information Leakage Defense**: All logs, API responses, and error envelopes strictly redact passwords, cryptographic secrets, authentication tokens, and internal stack traces.
4. **Tamper-Evident Chronological Auditing**: Every regulatory touchpoint is permanently recorded with actor identity, timestamp, IP address, and contextual metadata.

---

## 2. Authentication Architecture

### 2.1 Password Security
- **Algorithm**: `bcrypt` (Blowfish-based key derivation) with an adaptive cost factor of 12 rounds.
- **Salting**: Cryptographically secure, unique 128-bit salt generated per password automatically by `passlib.context.CryptContext`.
- **Pre-Hashing Truncation Protection**: Passwords are UTF-8 validated prior to hashing.
- **Anti-Enumeration Responses**: Authentication failures on `/api/v1/auth/login` return generic `401 Unauthorized` messages ("*Invalid government email or security password*") regardless of whether the email existed or the password mismatched.

### 2.2 Token Security (JWT)
- **Algorithm**: HMAC-SHA256 (`HS256`) with a cryptographically random 256-bit secret key.
- **Mandatory Claims**:
  - `sub`: Unique officer UUID (`str(user.id)`).
  - `iss`: Authoritative issuer claim set to `drishti.gov.in`.
  - `iat`: Epoch timestamp of token generation.
  - `exp`: Explicit expiration boundary (standard session lifetime: 24 hours).
  - Custom claims: `email`, `role`, `badge_id`, `state`, `district`.
- **Validation**:
  - Tokens are decoded and validated on every protected API call using FastAPI dependency injection (`get_current_user`).
  - Tokens lacking the verified `iss="drishti.gov.in"` or expired tokens are rejected immediately with `401 Unauthorized` and `WWW-Authenticate: Bearer` challenge headers.

### 2.3 Session Handling & Account State
- **Stateless Verification**: Bearer tokens are stateless, enabling horizontal scaling behind government load balancers.
- **Active Account Check**: Prior to fulfilling any authenticated request, the officer record is resolved in PostgreSQL; if `is_active == False`, the request is terminated with `403 Forbidden` ("*Authority account is inactive or revoked*").
- **Logout Invalidation**: Logout requests (`POST /api/v1/auth/logout`) commit a statutory `USER_LOGOUT` audit log entry, terminating the client session.

---

## 3. Authorization & Role-Based Access Control (RBAC)

### 3.1 Role Hierarchy
DRISHTI enforces an explicit statutory role hierarchy:

```
ADMIN
  └── SUPERVISOR
        └── AUTHORITY_OFFICER
              └── REVIEWER / ANALYST
```

| Role | Permissions & Scope |
| :--- | :--- |
| **`ADMIN`** | System-wide administrative configuration, user provisioning, role promotion, global audit log inspection. |
| **`SUPERVISOR`** | Regional supervision, case reassignment, priority triage overrides, batch action approvals. |
| **`AUTHORITY_OFFICER`** | Statutory enforcement: review evidence, issue Sec 32 notices, order inspections/lab testing, generate signed compliance reports. |
| **`REVIEWER`** | Analytical review: submit initial observations, highlight conflicting evidence, draft preliminary notes. |

### 3.2 Enforcement Guards
All routes enforce role requirements using modular dependency functions in `app.api.deps`:
- `get_current_user`: Base requirement — verifies valid JWT and active account.
- `require_authority_officer`: Enforces role is in `[AUTHORITY_OFFICER, SUPERVISOR, ADMIN]`.
- `require_supervisor`: Enforces role is in `[SUPERVISOR, ADMIN]`.
- `require_admin`: Enforces role is `ADMIN`.

Unauthorized attempts return `403 Forbidden` with descriptive regulatory denial explanations.

---

## 4. Input & File Security

### 4.1 Ingestion Validation
- **Request Models**: All inbound JSON payloads are strictly validated against Pydantic models with type constraints, regex validators, and bounded strings.
- **URL Validation**: External product links are parsed using `urllib.parse` and regex validators:
  - Allowed schemes: Strictly `http` and `https`.
  - Rejection: Reject localhost, loopback, file URIs, and malformed network locations.

### 4.2 File Upload & Image Security
Evidence packaging images (packaging, nutrition tables, ingredient labels) are safeguarded against upload exploitation:
1. **MIME Type Whitelist**: Only `image/jpeg`, `image/png`, and `image/webp` are permitted. All executables, SVG scripts, and arbitrary binary payloads are rejected with `400 Bad Request`.
2. **Empty File Detection**: Files with 0 bytes are rejected immediately.
3. **File Size Restriction**: Enforced hard limit of **15 MB** (15,728,640 bytes) per image file. Uploads exceeding this boundary are aborted with `400 Bad Request`.
4. **Path Traversal Prevention**: Client-supplied filenames are stripped entirely. Files are stored using cryptographic UUIDs (`uuid.uuid4().hex`) combined with verified extensions, fully mitigating `../`, `..\\`, and null-byte injection exploits.

---

## 5. Database Security & Query Protection

### 5.1 Parameterized Queries (SQLAlchemy 2.0)
- **100% Parameterization**: All database interactions use SQLAlchemy 2.0 ORM expressions (`select(...)`, `update(...)`, `delete(...)`) or parameterized query builders.
- **Zero Raw SQL Concatenation**: No user input or dynamic string formatting is ever concatenated into raw SQL strings.
- **ORM Escaping**: All text filters (product name search, brand search, case status) are bound as parameters via asyncpg drivers, preventing SQL injection (SQLi).

### 5.2 Transactional Boundaries
- Database sessions run within scoped `AsyncSession` context managers (`get_db`).
- Unhandled exceptions automatically trigger rollbacks, preserving database consistency and preventing partial state corruption.

---

## 6. API Security & Transport Defense

### 6.1 Rate Limiting (`SlidingWindowRateLimiter`)
To protect sensitive endpoints (e.g. `/api/v1/auth/login`, ingestion gateways) against brute-force credential stuffing and denial-of-service:
- **Architecture**: Thread-safe in-memory sliding window limiter (`app.core.rate_limit.SlidingWindowRateLimiter`).
- **Keying**: Client IP address or authenticated subject identifier.
- **Response**: Upon threshold violation, the API responds with `HTTP 429 Too Many Requests`, a structured error payload, and a standard `Retry-After: <seconds>` HTTP header.
- **Default Policy**: 30 requests per minute on authentication endpoints.

### 6.2 CORS Policy (Cross-Origin Resource Sharing)
- Scoped strictly via `CORSMiddleware`.
- Permitted origins are restricted to configured hostnames (e.g. authorized official frontend applications).
- Pre-flight caching and credential propagation (`allow_credentials=True`) are tightly scoped.

### 6.3 Error Handling & Information Leakage Prevention
- **Structured Error Envelope**: All API exceptions format responses through `format_error_response`:
  ```json
  {
    "status": 401,
    "error_code": "HTTP_401",
    "message": "Invalid government email or security password",
    "path": "/api/v1/auth/login",
    "timestamp": "2026-09-04T06:00:00.000000Z",
    "details": {}
  }
  ```
- **Internal Server Errors (`500`)**: When `DEBUG=False` in production, internal stack traces and database exception messages are omitted, preventing internal environment disclosure.

---

## 7. Tamper-Evident Audit Logging

### 7.1 Statutory Event Registry
The `AuditLog` table permanently captures all significant regulatory events:

| Event Identifier | Trigger Condition | Logged Metadata |
| :--- | :--- | :--- |
| `USER_LOGIN` | Officer successfully authenticates | Officer ID, badge, email, role, IP, timestamp |
| `USER_LOGOUT` | Officer terminates session | Officer ID, badge, email, IP, timestamp |
| `CASE_CREATED` | New regulatory case initiated | Case ID, case number, product ID, priority |
| `PRODUCT_SUBMITTED` | Ingestion of product URL/images | Case ID, case number, product details, image count |
| `DEEP_ANALYSIS_COMPLETED` | Execution of multi-source cross-referencing | Case ID, claims count, OCR entities analyzed |
| `CONSISTENCY_CHECK_COMPLETED` | OCR vs. metadata verification completed | Case ID, conflict count, mismatch flags |
| `RISK_ASSESSMENT_COMPLETED` | Risk score and level calculated | Case ID, risk score, risk level, confidence |
| `CASE_TRIAGED_ROUTING` | Automated workflow routing (Priority vs. Standard) | Case ID, initial status, target status, reason |
| `CASE_STATUS_UPDATED` | Officer changes case lifecycle state | Case ID, previous status, new status, statutory reason |
| `CASE_REVIEW_STARTED` | Officer initiates formal evidence review | Case ID, officer badge, start timestamp |
| `CASE_REVIEW_RECORDED` | Officer issues statutory action/notice | Case ID, action enum, legal remarks, officer badge |
| `REPORT_GENERATED_PDF` | Officer downloads signed PDF intelligence report | Case ID, report ID, risk score, byte size, officer badge |
| `REPORT_GENERATED_HTML` | Officer inspects formatted HTML compliance brief | Case ID, report ID, officer badge |

### 7.2 Zero-Exposure Guarantee
The audit logging engine strictly excludes:
- Passwords or password hashes.
- Bearer tokens or refresh tokens.
- Cryptographic private keys or database credentials.

### 7.3 Audit Trail Verification Endpoint
Authorized officers can inspect the complete chronological audit chain for any case:
```
GET /api/v1/cases/{case_id}/audit-trail
Authorization: Bearer <TOKEN>
```
Returns a chronological list of all actions, timestamps, and actor identifiers from initial submission to final adjudication.

---

## 8. Summary of Security Verification Tests

The platform includes automated security regression tests (`backend/tests/test_security_and_access.py`):
1. **Unauthenticated Access**: Verifies protected endpoints reject missing tokens with `401`.
2. **Invalid / Expired JWT**: Verifies forged or expired tokens are rejected with `401`.
3. **Deactivated Account**: Verifies revoked officer accounts return `403`.
4. **RBAC Enforcement**: Verifies insufficient roles return `403`.
5. **MIME Whitelist**: Verifies `.exe`, `.svg`, or `.sh` uploads return `400`.
6. **File Size Protection**: Verifies payloads > 15 MB return `400`.
7. **Empty File Defense**: Verifies 0-byte uploads return `400`.
8. **Rate Limiting**: Verifies rapid repeated hits trigger `429 Too Many Requests` with `Retry-After`.
9. **Credential Redaction**: Verifies audit logs contain zero plaintext passwords or secrets.
10. **Case Audit Trail**: Verifies chronological ordering and event capture on regulatory workflows.
