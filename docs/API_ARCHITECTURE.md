# DRISHTI: API Architecture & Endpoint Specifications
## Phase 0: RESTful, Streaming & Event-Driven API Contract

---

### 1. API Architecture Overview

The DRISHTI API is designed around RESTful principles for transactional management, combined with **Server-Sent Events (SSE)** and **WebSockets** for real-time pipeline status updates.

- **Base URL**: `/api/v1`
- **Protocol**: HTTPS (TLS 1.3 mandatory), WebSockets (`wss://`)
- **Data Format**: JSON (`application/json`), Multipart Form (`multipart/form-data` for media)
- **Standard Authentication**: `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Character Encoding**: UTF-8

---

### 2. Authentication, Authorization & RBAC

All endpoints enforce strict Role-Based Access Control (RBAC) mapped to regulatory statutory hierarchy:

| Role Identifier | Description | Permitted Capabilities |
|---|---|---|
| `SUPER_ADMIN` | System Administrators | User provisioning, audit log inspection, global system config |
| `CENTRAL_ANALYST` | FSSAI HQ Intelligence Officers | Bulk ingestion, cross-national analytics, rule configuration |
| `DESIGNATED_OFFICER` | District Regulatory Heads | Case review, issuing Section 32 orders, assigning field FSOs |
| `FOOD_SAFETY_OFFICER`| Field Inspectors (FSO) | Image upload, field triage, sampling logs, local case review |
| `LEGAL_AUDITOR` | Regulatory Legal Counsel | Read-only certified dossier export, chain-of-custody verification |

---

### 3. Comprehensive API Module Groups

```
/api/v1
  ├── /auth               # Authentication, token refresh, passwordless magic links
  ├── /products           # Product submission, catalog browsing, metadata
  ├── /extraction         # Vision, OCR status, zone bounding boxes, raw tokens
  ├── /compliance         # Rules execution, ingredient checks, claim analysis
  ├── /discrepancies      # Cross-source differential matrix (Web vs Label vs FoSCoS)
  ├── /risk               # Risk scoring, priority queues, district heatmaps
  ├── /dossiers           # Evidence dossier generation, certified PDF/A download
  ├── /cases              # Regulatory case workflow, FSO assignment, enforcement
  ├── /foscos             # FoSCoS registry verification & lookup
  └── /admin              # Regulatory rulesets, system metrics, audit logs
```

---

### 4. Detailed Endpoint Specifications

#### 4.1 Module: Authentication (`/auth`)

##### `POST /api/v1/auth/login`
- **Description**: Authenticate regulatory officer via credentials and TOTP / Gov SSO.
- **Request Body**:
```json
{
  "email": "fso.sharma@fssai.gov.in",
  "password": "SecurePassword123!",
  "totp_code": "482910"
}
```
- **Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "u-4982-fso",
    "name": "Rajesh Sharma",
    "badge_id": "FSO-DL-CENTRAL-012",
    "role": "FOOD_SAFETY_OFFICER",
    "jurisdiction_state": "DL",
    "jurisdiction_district": "DL-CENTRAL"
  }
}
```

---

#### 4.2 Module: Products & Ingestion (`/products`)

##### `POST /api/v1/products/ingest/url`
- **Description**: Submit an e-commerce food product URL for automated headless scraping and compliance audit.
- **Headers**: `Authorization: Bearer <TOKEN>`
- **Request Body**:
```json
{
  "url": "https://www.quickgrocery.in/p/miracle-keto-slimming-shake-500g",
  "source_platform": "QUICK_COMMERCE",
  "priority": "HIGH",
  "district_code": "DL-CENTRAL"
}
```
- **Response `202 Accepted`**:
```json
{
  "job_id": "job-8921b-scrape",
  "product_id": "prod-5521-keto-shake",
  "status": "QUEUED",
  "estimated_duration_seconds": 12,
  "status_stream_url": "/api/v1/products/prod-5521-keto-shake/events"
}
```

##### `POST /api/v1/products/ingest/images`
- **Description**: Multi-part upload of physical packaging images (Front, Back, Side, Nutritional Panel, License Stamp).
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `declared_name` (string): "Herbal Vitality Protein"
  - `declared_brand` (string): "AyurNutra"
  - `front_image` (file binary): PNG / JPEG (Front of Pack)
  - `back_image` (file binary): PNG / JPEG (Back of Pack / Ingredients)
  - `license_panel_image` (file binary, optional): PNG / JPEG
  - `district_code` (string): "KA-BLR-URBAN"
- **Response `202 Accepted`**:
```json
{
  "job_id": "job-9932-vision-ocr",
  "product_id": "prod-7712-herbal-vitality",
  "artifacts_registered": [
    { "type": "FOP_IMAGE", "sha256": "4a7d...391a", "uri": "s3://drishti-raw/img1.jpg" },
    { "type": "BOP_IMAGE", "sha256": "8b2e...11cc", "uri": "s3://drishti-raw/img2.jpg" }
  ],
  "status": "PROCESSING"
}
```

##### `GET /api/v1/products/{product_id}/events`
- **Description**: Server-Sent Events (SSE) stream providing real-time telemetry of pipeline progression.
- **Protocol**: HTTP SSE (`text/event-stream`)
- **Event Output Stream**:
```
event: pipeline_progress
data: {"stage": "SCRAPING", "percent": 100, "message": "Scraped DOM parsed successfully"}

event: pipeline_progress
data: {"stage": "OCR_PROCESSING", "percent": 65, "message": "Detected 4 label zones, executing OCR"}

event: pipeline_completed
data: {"product_id": "prod-7712", "risk_tier": "HIGH", "composite_score": 78.4}
```

---

#### 4.3 Module: Extraction & Vision (`/extraction`)

##### `GET /api/v1/extraction/{product_id}`
- **Description**: Retrieve raw extracted zones, bounding box coordinates, and detected text tokens.
- **Response `200 OK`**:
```json
{
  "product_id": "prod-7712",
  "zones": [
    {
      "zone_id": "zone-01",
      "zone_type": "NUTRITIONAL_FACTS",
      "bounding_box": { "x_min": 120, "y_min": 450, "x_max": 820, "y_max": 1240 },
      "crop_url": "https://storage.drishti.gov.in/crops/prod-7712-nutr.jpg",
      "confidence": 0.965,
      "extracted_data": {
        "energy_kcal": 410,
        "protein_g": 2.1,
        "total_sugars_g": 34.0,
        "added_sugars_g": 28.0
      }
    },
    {
      "zone_id": "zone-02",
      "zone_type": "VEG_NONVEG_LOGO",
      "bounding_box": { "x_min": 850, "y_min": 1100, "x_max": 920, "y_max": 1170 },
      "crop_url": "https://storage.drishti.gov.in/crops/prod-7712-logo.jpg",
      "confidence": 0.991,
      "symbol_detected": "BROWN_TRIANGLE_NON_VEG"
    }
  ]
}
```

---

#### 4.4 Module: Compliance & Rules (`/compliance`)

##### `GET /api/v1/compliance/{product_id}/evaluate`
- **Description**: Trigger or retrieve comprehensive FSSAI compliance evaluation against statutory rulesets.
- **Response `200 OK`**:
```json
{
  "product_id": "prod-7712",
  "overall_compliance": "NON_COMPLIANT",
  "total_violations_count": 3,
  "violations": [
    {
      "violation_id": "viol-001",
      "rule_code": "FSSAI-ADV-2018-SEC4-SUG",
      "severity": "HIGH",
      "statutory_reference": "Regulation 4(1), FSS (Advertising and Claims) Regulations, 2018",
      "violation_title": "Illegal 'Sugar Free' claim on high added-sugar product",
      "explanation": "Front of pack claims 'Zero Sugar', but nutritional analysis reveals 28g added sugar per 100g. Threshold for Sugar Free is <= 0.5g per 100g.",
      "evidence_zone_ref": "zone-01"
    },
    {
      "violation_id": "viol-002",
      "rule_code": "FSSAI-LBL-2020-ALLERGEN",
      "severity": "CRITICAL",
      "statutory_reference": "Regulation 5(3)(b), FSS (Labelling and Display) Regulations, 2020",
      "violation_title": "Omission of mandatory allergen declaration",
      "explanation": "Ingredient list contains Soy Protein Isolate, but packaging lacks the mandatory warning 'Contains Soy'.",
      "evidence_zone_ref": "zone-03"
    }
  ]
}
```

---

#### 4.5 Module: Cross-Source Discrepancies (`/discrepancies`)

##### `GET /api/v1/discrepancies/{product_id}`
- **Description**: Returns 3-way discrepancy matrix comparing Web Catalog vs Physical Label vs FoSCoS Registry.
- **Response `200 OK`**:
```json
{
  "product_id": "prod-7712",
  "discrepancies_detected": true,
  "matrix": [
    {
      "attribute": "Nutritional Claim: Protein",
      "web_claim": "High Protein 25g per serving",
      "packaging_label": "2.1g per serving",
      "foscos_record": "Category: Cereal Based Confectionery (Low Protein)",
      "mismatch_severity": "CRITICAL",
      "inference": "E-Commerce portal exaggerates protein content by over 1000% to mislead health-conscious consumers."
    }
  ]
}
```

---

#### 4.6 Module: Risk & Dossiers (`/risk`, `/dossiers`)

##### `GET /api/v1/risk/queue`
- **Description**: Triage queue for Designated Officers, sorted by risk score priority.
- **Query Params**: `state=DL&district=DL-CENTRAL&min_risk=70&status=TRIAGE_READY`
- **Response `200 OK`**:
```json
{
  "total_items": 14,
  "items": [
    {
      "product_id": "prod-7712",
      "product_name": "Herbal Vitality Protein",
      "brand_name": "AyurNutra",
      "composite_risk_score": 88.5,
      "risk_tier": "CRITICAL",
      "primary_violation": "Illegal Superlative Health Claim + Undeclared Allergen",
      "submission_timestamp": "2026-09-03T18:30:00Z"
    }
  ]
}
```

##### `GET /api/v1/dossiers/{product_id}/export`
- **Description**: Generate and stream certified statutory Evidence Dossier PDF/A.
- **Response**: `200 OK`
  - `Content-Type`: `application/pdf`
  - `Content-Disposition`: `attachment; filename="DOSSIER_DL_2026_0912.pdf"`
  - `X-Drishti-SHA256`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

---

#### 4.7 Module: Regulatory Cases & Workflow (`/cases`)

##### `POST /api/v1/cases/{case_id}/action`
- **Description**: Officer executes regulatory action (Assign FSO, Issue Sec 32 Notice, Close Case).
- **Request Body**:
```json
{
  "action_type": "ISSUE_IMPROVEMENT_NOTICE",
  "statutory_section": "SECTION_32",
  "compliance_window_days": 14,
  "assigned_fso_id": "u-4982-fso",
  "official_notes": "Immediate recall of batch AY-2026-08 from e-commerce sellers mandated."
}
```
- **Response `200 OK`**:
```json
{
  "case_id": "case-2026-041",
  "status": "NOTICE_ISSUED_SEC32",
  "notice_reference_number": "FSSAI/NTC/2026/DL-0941",
  "action_timestamp": "2026-09-03T20:20:00Z"
}
```

---

### 5. Standard Error Handling & Response Contracts

The API conforms to RFC 7807 (Problem Details for HTTP APIs):

```json
{
  "type": "https://api.drishti.gov.in/errors/INVALID_FSSAI_LICENSE",
  "title": "Invalid FSSAI License Checksum",
  "status": 422,
  "detail": "The license number '11002233' contains 8 digits. FSSAI requires exactly 14 numeric digits conforming to FoSCoS schema.",
  "instance": "/api/v1/compliance/verify-license",
  "error_code": "ERR_FSSAI_LIC_LENGTH",
  "timestamp": "2026-09-03T20:20:05Z"
}
```

#### Standard HTTP Status Mapping:
- `200 OK`: Request succeeded synchronously.
- `201 Created`: Resource successfully created.
- `202 Accepted`: Long-running task accepted (returns `job_id`).
- `400 Bad Request`: Malformed syntax or missing query parameters.
- `401 Unauthorized`: Missing or expired JWT.
- `403 Forbidden`: Officer role lacks jurisdiction or statutory clearance.
- `404 Not Found`: Resource does not exist.
- `422 Unprocessable Entity`: Validation failure on input schema.
- `429 Too Many Requests`: Rate limit exceeded (Leaky Bucket policy).
- `500 Internal Server Error`: Unhandled server exception (logged with trace ID).
