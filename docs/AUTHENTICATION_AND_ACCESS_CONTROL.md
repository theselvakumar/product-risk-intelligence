# DRISHTI: Authentication & Authority Access Control
## Phase 3: Security Specifications, RBAC Hierarchy & Audit Logging

---

### 1. Security Architecture Overview

DRISHTI is strictly an **authority-facing surveillance system**. There is no public consumer registration or self-service signup. All accounts represent statutory officials within regulatory food safety jurisdictions (FSSAI, state food safety departments, district licensing authorities).

```
+---------------------------------------------------------------------------------------------------+
|                                 AUTHORITY AUTHENTICATION TOPOLOGY                                 |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ Authority Officer Client ]                     [ DRISHTI Backend Gateway ]                     |
|            │                                                    │                                 |
|            │  1. POST /auth/login (email, password)             │                                 |
|            ├───────────────────────────────────────────────────>│                                 |
|            │                                                    │ 2. Lookup user & verify bcrypt  |
|            │                                                    │    Check is_active              |
|            │                                                    │ 3. Generate HS256 JWT Token     |
|            │                                                    │ 4. Insert AuditLog (USER_LOGIN) |
|            │  5. 200 OK { access_token, user_profile }          │                                 |
|            │<───────────────────────────────────────────────────┤                                 |
|            │                                                    │                                 |
|            │  6. GET /auth/me or GET /api/v1/cases/triage       │                                 |
|            │     (Header: Authorization: Bearer <JWT>)          │                                 |
|            ├───────────────────────────────────────────────────>│                                 |
|            │                                                    │ 7. Decode JWT, check exp/iss    |
|            │                                                    │ 8. Resolve User & enforce RBAC  |
|            │  9. 200 OK { current_user / triage_data }          │                                 |
|            │<───────────────────────────────────────────────────┤                                 |
|            │                                                    │                                 |
|            │  10. POST /auth/logout                             │                                 |
|            ├───────────────────────────────────────────────────>│                                 |
|            │                                                    │ 11. Insert AuditLog(USER_LOGOUT)|
|            │  12. 200 OK { message: "logged out" }              │                                 |
|            │<───────────────────────────────────────────────────┤                                 |
+---------------------------------------------------------------------------------------------------+
```

---

### 2. Role-Based Access Control (RBAC) Matrix

| User Role | Description | Current / Future Status | Capabilities & Clearance |
|---|---|---|---|
| `AUTHORITY_OFFICER` | Food Safety Officers (FSO) & Field Inspectors | **Active (Initial Role)** | Access triage queues, view assigned cases, record sampling logs, request notices. |
| `ADMIN` | System Administrators & IT Security Officers | Prepared Architecturally | User provisioning, role assignment, audit log inspection, global configuration. |
| `SUPERVISOR` | District Designated Officers (DO) | Prepared Architecturally | Sign Section 32 Improvement Notices, assign cases to territorial FSOs, approve retests. |
| `REVIEWER` | Legal Officers & Appellate Auditors | Prepared Architecturally | Review certified evidence dossiers, verify chain-of-custody hashes, tribunal submissions. |

---

### 3. Cryptographic Security & Credentials Handling

1. **Password Hashing**:
   - Algorithm: **Bcrypt** with dynamic 12-round salt (`bcrypt.gensalt(12)`).
   - Plain-text passwords are never stored in databases, caches, logs, or network payloads.
2. **JWT Access Tokens**:
   - Algorithm: **HMAC-SHA256 (HS256)**.
   - Mandatory Claims: `sub` (User UUID), `exp` (Expiry), `iat` (Issued at), `iss` (`drishti.gov.in`).
   - Context Claims: `email`, `role`, `badge_id`, `state`, `district`.
   - Expiration: Configurable (default 24 hours).
3. **Audit Logging**:
   - Every login and logout event writes an immutable record to `audit_logs` with client IP, badge ID, timestamp, and action (`USER_LOGIN`, `USER_LOGOUT`).

---

### 4. API Endpoints Contract

#### 4.1 Login Endpoint
- **Method & Path**: `POST /auth/login` (also `/api/v1/auth/login`)
- **Request Body**:
  ```json
  {
    "email": "officer@drishti.gov.in",
    "password": "AuthorityOfficer2026!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "52bae1dc-2067-40ce-9f8e-7700aeb117e2",
      "email": "officer@drishti.gov.in",
      "full_name": "Rajesh Sharma (Food Safety Officer)",
      "badge_id": "FSO-DL-CENTRAL-012",
      "role": "AUTHORITY_OFFICER",
      "jurisdiction_state": "DL",
      "jurisdiction_district": "DL-CENTRAL",
      "is_active": true
    }
  }
  ```

#### 4.2 Current User Profile
- **Method & Path**: `GET /auth/me` (also `/api/v1/auth/me`)
- **Header**: `Authorization: Bearer <ACCESS_TOKEN>`
- **Response `200 OK`**:
  ```json
  {
    "user": {
      "id": "52bae1dc-2067-40ce-9f8e-7700aeb117e2",
      "email": "officer@drishti.gov.in",
      "full_name": "Rajesh Sharma (Food Safety Officer)",
      "badge_id": "FSO-DL-CENTRAL-012",
      "role": "AUTHORITY_OFFICER",
      "jurisdiction_state": "DL",
      "jurisdiction_district": "DL-CENTRAL",
      "is_active": true
    }
  }
  ```

#### 4.3 Logout Endpoint
- **Method & Path**: `POST /auth/logout` (also `/api/v1/auth/logout`)
- **Header**: `Authorization: Bearer <ACCESS_TOKEN>`
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Officer Rajesh Sharma (Food Safety Officer) (FSO-DL-CENTRAL-012) logged out successfully"
  }
  ```

---

### 5. Development Seed Authority Officer

For developer convenience and automated testing, a default authority seed user is automatically maintained:

- **Email**: `officer@drishti.gov.in`
- **Password**: `AuthorityOfficer2026!`
- **Full Name**: `Rajesh Sharma (Food Safety Officer)`
- **Badge ID**: `FSO-DL-CENTRAL-012`
- **Role**: `AUTHORITY_OFFICER`
- **Jurisdiction**: `DL-CENTRAL, Delhi`
