# DRISHTI Platform — Comprehensive Testing Strategy & Verification Guide

**Document Version:** 1.0.0  
**Effective Date:** September 2026  
**Classification:** Official Regulatory Verification Standard — FSSAI Digital Surveillance  
**Applicability:** DRISHTI Core Backend, Intelligence Modules, and API Gateways

---

## 1. Testing Philosophy & Regulatory Rigor

The **DRISHTI** surveillance platform operates under strict statutory standards where analysis outputs form the basis of formal enforcement notices under Section 32 of the Food Safety and Standards Act (FSSA 2006). The automated test suite is therefore engineered with four core testing mandates:

1. **Deterministic Regulatory Logic**: Rule matching, allergen cross-referencing, additive status, and mathematical risk scoring must yield identical, reproducible results for given inputs without non-deterministic drift.
2. **Strict Segregation of AI Advisory Findings**: Tests strictly verify that AI statements are cryptographically attributed, marked as advisory, and prevented from automatically executing statutory penalties or closing cases.
3. **Information Security & Leakage Prevention**: Negative tests verify that credentials, secret keys, bearer tokens, and internal stack traces are zero-exposed across logs, error envelopes, and API payloads.
4. **End-to-End Statutory Traceability**: Every finding must trace backwards from legal citation to extracted text, and ultimately to immutable raw source evidence (URLs, physical packaging photos).

---

## 2. Test Architecture & Taxonomy

The backend test suite is organized into 15 dedicated modules located in `backend/tests/`:

| Module | Purpose & Scope | Tests Count |
| :--- | :--- | :---: |
| `test_auth.py` | JWT generation, bcrypt validation, session invalidation, inactive account denial | 7 |
| `test_cases.py` | Case ingestion (URLs, descriptions, image files), metrics calculation, status updates | 12 |
| `test_consistency.py` | Cross-source comparison (Web claims vs. physical packaging OCR), mismatch flagging | 9 |
| `test_database.py` | PostgreSQL/SQLite connection pools, session rollbacks, schema migrations | 3 |
| `test_deep_analysis.py` | 5-module regulatory checks: claims, additives, licenses, allergens, manufacturers | 6 |
| `test_evidence.py` | Evidence package assembly, source tracking, SHA-256 integrity checks, AI separation | 6 |
| `test_explainability.py` | Legal citation trees, severity ordering (CRITICAL → INFO), explainable factor summaries | 6 |
| `test_health.py` | System health probes, database latency telemetry, version metadata | 4 |
| `test_intelligence.py` | Product normalization, ingredient tokenization, INS additive detection, entity deduplication | 5 |
| `test_ocr.py` | Image preprocessing, multi-zone OCR text extraction, image quality scoring | 5 |
| `test_priority_workflow.py`| Automated triage routing, priority review queue, statutory reviewer decisions | 8 |
| `test_report_generation.py`| 8-section compliance report generation, HTML brief rendering, ReportLab PDF generation | 6 |
| `test_risk_engine.py` | Multi-factor risk scoring engine, confidence score calculation, risk level bounds | 9 |
| `test_security_and_access.py`| Token tampering rejection, RBAC restrictions, 15MB file caps, rate limiter (429) | 12 |
| `test_end_to_end_integration.py`| Complete 13-stage sequential regulatory workflow test from login to signed PDF | 1 |
| **Total** | **Comprehensive Full Platform Coverage** | **99** |

---

## 3. Test Execution Instructions

### 3.1 Prerequisites
- Python 3.11+ (Python 3.14 compatible)
- Active virtual environment or direct Python interpreter
- All dependencies installed via `backend/requirements.txt`

### 3.2 Running the Full Test Suite
To execute all 99 automated tests with summary reporting:
```bash
cd backend
python -m pytest
```

### 3.3 Running with Verbose Output & Execution Timing
```bash
python -m pytest -v --durations=10
```

### 3.4 Running Specific Functional Test Suites
- **End-to-End Integration**:
  ```bash
  python -m pytest tests/test_end_to_end_integration.py -v
  ```
- **Security, RBAC & Rate Limiting**:
  ```bash
  python -m pytest tests/test_security_and_access.py -v
  ```
- **Report Generation (PDF & HTML)**:
  ```bash
  python -m pytest tests/test_report_generation.py -v
  ```
- **Priority Review Queue & Triage**:
  ```bash
  python -m pytest tests/test_priority_workflow.py -v
  ```

---

## 4. Test Fixtures & Database Isolation

### 4.1 Async In-Memory SQLite Isolation
All test modules operate on isolated, temporary SQLite databases via `aiosqlite` (`test_*.db`), created and torn down per test module:
- Automatic schema creation using `Base.metadata.create_all`.
- Automatic teardown and file cleanup via `pytest.fixture(scope="module", autouse=True)`.
- Scoped `AsyncSessionLocal` session factories overriding `get_db` FastAPI dependency.

### 4.2 Realistic Multi-Modal Test Data Generators
- **Synthetic High-Contrast Label Generator**:
  `create_clear_label_image()` in `test_ocr.py` and `test_end_to_end_integration.py` leverages Pillow (`PIL.Image`, `PIL.ImageDraw`) to render synthetic packaging labels containing realistic ingredients, net quantity, and 14-digit FSSAI licenses for OCR decoding.
- **Statutory Officer Personas**: Pre-seeded active officers (`AUTHORITY_OFFICER`), supervisors (`SUPERVISOR`), and restricted analysts (`REVIEWER`) with verified badge identifiers.

---

## 5. Summary of Tested Regulatory Invariants

1. **Authentication Invariant**: An unauthenticated or forged request to any protected route strictly yields `HTTP 401 Unauthorized`.
2. **Revocation Invariant**: A deactivated officer account (`is_active=False`) strictly yields `HTTP 403 Forbidden`.
3. **RBAC Invariant**: A user with role `REVIEWER` attempting to issue an improvement notice or alter statutory status strictly yields `HTTP 403 Forbidden`.
4. **Input Size Invariant**: File uploads exceeding 15 MB or having disallowed MIME types (`.exe`, `.svg`) strictly yield `HTTP 400 Bad Request`.
5. **AI Separation Invariant**: No AI-generated statement can be recorded as primary physical evidence; AI statements are tagged with `ai_generated=True` and origin `AI_ANALYSIS`.
6. **No Automatic Penalty Invariant**: Case closing or statutory notice issuance requires affirmative human authority determination (`CaseReview`).
7. **Report Integrity Invariant**: All compliance PDF dossiers include SHA-256 verification seals, non-delegable statutory disclaimers, and ReportLab binary headers (`%PDF`).
8. **Audit Trail Invariant**: Every lifecycle change produces an immutable `AuditLog` row with zero exposure of credentials or secrets.
