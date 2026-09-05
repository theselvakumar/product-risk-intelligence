# DRISHTI: AI-Powered Food Product Compliance & Risk Intelligence Platform

[![Production Status](https://img.shields.io/badge/Status-Production%20Ready%20(Phase%2017)-emerald?style=flat-square)](docs/FINAL_SYSTEM_OVERVIEW.md)
[![Tests](https://img.shields.io/badge/Tests-99%2F99%20Passing%20(100%25)-brightgreen?style=flat-square)](docs/TESTING.md)
[![Backend](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&style=flat-square)](https://fastapi.tiangolo.com)
[![Frontend](https://img.shields.io/badge/Next.js-16%20(Turbopack)-black?logo=next.js&style=flat-square)](https://nextjs.org)
[![Database](https://img.shields.io/badge/PostgreSQL-16%20Async-336791?logo=postgresql&style=flat-square)](https://www.postgresql.org)
[![Security](https://img.shields.io/badge/RBAC-Statutory%20Guards-orange?style=flat-square)](docs/SECURITY.md)

---

## 1. Statutory Mandate & System Overview

**DRISHTI** (*Digital Regulatory Intelligence & Surveillance for Holistic Threat Identification*) is an enterprise compliance surveillance and evidentiary decision-support platform engineered for food safety authorities: the **Food Safety and Standards Authority of India (FSSAI)**, State Food Safety Administrations, Designated Officers, and Food Safety Officers (FSOs).

The platform triages non-compliant food products across e-commerce marketplaces and physical packaging by executing an automated 13-stage statutory intelligence pipeline:
- **Multi-Modal Ingestion**: Ingests product URLs, physical packaging images (FOP/BOP), and officer observations with cryptographic SHA-256 digests.
- **Multi-Zone OCR & Text Extraction**: Extracts text across packaging zones, identifying FSSAI licenses, nutrition tables, and ingredient lists.
- **Product Normalization**: Structures raw data into canonical product SKUs, resolving INS additive numbers and allergen disclosures.
- **Deep Regulatory Analysis**: 5-modular dimensions evaluating prohibited disease-cure claims, unpermitted additives, and labeling violations.
- **Cross-Source Consistency**: Reconciles e-commerce marketing statements against physical packaging labels and official registries.
- **Multi-Factor Risk Scoring**: Deterministic, explainable scoring classifying products into statutory risk tiers (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Chain of Custody & Evidence**: Bundles findings with raw evidence without hallucination, strictly segregating advisory AI notes.
- **Priority Review Queue**: Triage queue enabling authority officers to review evidence, issue formal **Section 32 Improvement Notices**, and generate signed PDF compliance dossiers.

---

## 2. Complete End-to-End Regulatory Lifecycle

```
[ Authority Login ] ──► [ Surveillance Dashboard ] ──► [ Submit Product (URL / Image / Desc) ]
                                                                      │
                                                                      ▼
[ Deep Analysis ] ◄── [ Product Structuring ] ◄── [ Multi-Zone OCR ] ◄─┘
       │
       ▼
[ Cross-Source Consistency ] ──► [ Risk Intelligence Engine ] ──► [ Traceable Explainability ]
                                                                             │
                                                                             ▼
[ Statutory Dossier (PDF) ] ◄── [ Authority Review (Sec 32) ] ◄── [ Priority Review Queue ]
```

---

## 3. Technology Stack & Key Frameworks

- **Backend**: Python 3.11+ / 3.14, FastAPI (ASGI), Async Uvicorn, Pydantic v2.
- **Database & ORM**: PostgreSQL 16, SQLAlchemy 2.0 Async ORM with 100% Parameterized Queries.
- **Image Processing & OCR**: OpenCV, Pillow (PIL), NumPy, Multi-Zone OCR Pipeline.
- **Frontend**: Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS.
- **Document Compilation**: ReportLab (Vector PDF Dossiers with cryptographic seals), Jinja2 (HTML Briefs).
- **Security & RBAC**: Bcrypt (rounds=12), PyJWT (HS256 with mandatory `drishti.gov.in` claims), In-memory sliding-window rate limiting.

---

## 4. Repository Structure

```text
drishti/
├── backend/                       # FastAPI Backend Service
│   ├── app/
│   │   ├── api/                   # Versioned REST controllers & RBAC guards
│   │   ├── core/                  # Security, rate limiter, errors, storage
│   │   ├── database/              # Async engine, session management, seeders
│   │   ├── models/                # SQLAlchemy ORM database models
│   │   ├── schemas/               # Strongly-typed Pydantic schemas
│   │   └── services/              # Regulatory intelligence, OCR, risk, reporting
│   ├── requirements.txt           # Python dependencies
│   └── tests/                     # 15 automated test suites (99 tests)
│
├── frontend/                      # Next.js 16 Authority Web Portal
│   ├── app/                       # App Router routes (Dashboard, Cases, Priority, Reports)
│   ├── components/                # Reusable UI components & status badges
│   └── package.json               # Node.js dependencies & scripts
│
├── docs/                          # Comprehensive Technical & Regulatory Documentation
│   ├── FINAL_SYSTEM_OVERVIEW.md   # Final architecture, capabilities, and roadmap
│   ├── TESTING.md                 # Complete testing strategy & execution manual
│   ├── DEPLOYMENT.md              # Production deployment & infrastructure runbook
│   ├── SECURITY.md                # Security, RBAC, input validation & audit logging
│   ├── AI_PIPELINE.md             # Vision preprocessing, OCR, reasoning, and risk
│   ├── SYSTEM_ARCHITECTURE.md     # Module boundaries and architectural specifications
│   └── PROJECT_OVERVIEW.md        # Regulatory context and statutory alignment
│
├── docker/                        # Containerization & Orchestration
│   ├── docker-compose.yml         # Multi-container local & staging orchestration
│   ├── Dockerfile.backend         # Production backend container
│   └── Dockerfile.frontend        # Production frontend container
└── README.md                      # This document
```

---

## 5. Quickstart & Local Execution

### 5.1 Backend Setup
```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run database migrations / seed initial officer
python -c "import asyncio; from app.database.session import AsyncSessionLocal; from app.database.seed import seed_authority_officer; asyncio.run(seed_authority_officer(AsyncSessionLocal()))"

# 5. Start development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5.2 Frontend Setup
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
# Opens at http://localhost:3000
```

### 5.3 Default Authority Credentials
- **Email**: `officer@drishti.gov.in`
- **Password**: `AuthorityOfficer2026!`
- **Role**: `AUTHORITY_OFFICER`
- **Badge ID**: `FSO-DL-CENTRAL-012`

---

## 6. Testing & Quality Assurance

DRISHTI is backed by 15 automated test suites covering 99 test cases:

```bash
cd backend
python -m pytest -v
```

### Verification Highlights:
- **100% Pass Rate**: All 99 tests pass in ~35 seconds.
- **End-to-End Test**: `tests/test_end_to_end_integration.py` validates the complete 13-stage workflow from login to PDF dossier compilation.
- **Security Test**: `tests/test_security_and_access.py` validates RBAC barriers, rate limiting, and zero exposure of secrets in audit logs.
- **Frontend Build**: `npm run build` compiles all 11 routes cleanly with 0 TypeScript errors.

For complete test taxonomy and execution instructions, refer to [docs/TESTING.md](docs/TESTING.md).

---

## 7. Production Deployment

For complete infrastructure specifications, container deployment, NGINX SSL hardening, and disaster recovery procedures, refer to [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

```bash
cd docker
docker compose up -d
```

---

## 8. Documentation Sitemap

- [docs/FINAL_SYSTEM_OVERVIEW.md](docs/FINAL_SYSTEM_OVERVIEW.md) — Comprehensive System Overview
- [docs/TESTING.md](docs/TESTING.md) — Testing Strategy & Verification Guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Production Deployment & Infrastructure Runbook
- [docs/SECURITY.md](docs/SECURITY.md) — Security, Access Control & Auditability Architecture
- [docs/AI_PIPELINE.md](docs/AI_PIPELINE.md) — OCR, Intelligence & Risk Algorithms
- [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) — Clean Architecture & Module Boundaries
