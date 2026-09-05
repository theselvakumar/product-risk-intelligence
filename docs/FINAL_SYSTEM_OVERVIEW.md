# DRISHTI Platform — Final System Architecture, Capabilities & Production Overview

**Document Version:** 1.0.0  
**Effective Date:** September 2026  
**Classification:** Official System Specification — FSSAI Digital Surveillance Platform  
**Delivery Stage:** Phase 17 — Production Readiness Review

---

## 1. Executive Summary & Statutory Purpose

The **DRISHTI** (*Digital Regulatory Intelligence & Surveillance for Holistic Threat Identification*) platform is a dedicated, authority-facing regulatory surveillance platform engineered to empower the Food Safety and Standards Authority of India (FSSAI) and State Food Safety Administrations. 

DRISHTI automates the discovery, extraction, cross-source reconciliation, and risk scoring of non-compliant food products circulating in digital commerce marketplaces and physical retail channels. The platform serves as an evidentiary decision-support system to prepare statutory dossiers for formal regulatory notices under **Section 32 (Improvement Notices)** and **Section 24 (Restrictions on Misleading Advertisements and Deceptive Claims)** of the **Food Safety and Standards Act, 2006 (FSSA 2006)**.

---

## 2. Final Architecture Summary

DRISHTI is built on a clean, layered architectural pattern ensuring strict separation of concerns, deterministic statutory reasoning, and immutable evidence tracking:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AUTHORITY INTERFACE                              │
│         Next.js 16 (Turbopack) • TypeScript • Tailwind CSS • App Router     │
│   Dashboard • Submit Product • Priority Queue • Evidence Viewer • Reports   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / REST (JWT Auth)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FASTAPI BACKEND CORE                             │
│       Python 3.11+ (Python 3.14 Ready) • Async Uvicorn • Pydantic v2        │
│                                                                             │
│  [API Routing & Auth]       [Storage & Ingestion]     [Rate Limiter]        │
│  • JWT HMAC-SHA256          • 15 MB File Caps         • Sliding Window      │
│  • RBAC Hierarchy           • SHA-256 Digesting       • HTTP 429 Defense    │
│  • Audit Trail              • Path Sanitization       • Client IP Track     │
├─────────────────────────────────────────────────────────────────────────────┤
│                          REGULATORY INTELLIGENCE                            │
│                                                                             │
│  1. OCR Engine              2. Normalizer & Structuring                     │
│     • Multi-zone processing    • Tokenization & ingredient deduplication    │
│     • Quality assessment       • INS additive resolution                    │
│     • License detection        • Allergen identification                    │
│                                                                             │
│  3. Deep Regulatory Analysis 4. Cross-Source Consistency                    │
│     • Claims evaluation        • Web vs. Pack comparative analysis          │
│     • Prohibited additives     • Discrepancy flagging                       │
│     • Schedule compliance      • Confidence scoring                         │
│                                                                             │
│  5. Risk Intelligence Engine 6. Explainability & Evidence Tree              │
│     • Multi-factor scoring     • Statutory legal mapping                    │
│     • Severity weighting       • Verbatim finding trees                     │
│     • 4-tier risk classification                                            │
│                                                                             │
│  7. Evidence Package         8. Statutory Case Reports                      │
│     • SHA-256 seal integrity   • 8-section compliance model                 │
│     • Strict AI segregation    • Jinja2 HTML & ReportLab PDF                │
├─────────────────────────────────────────────────────────────────────────────┤
│                         DATA PERSISTENCE & AUDIT                            │
│     PostgreSQL 16 Async (SQLAlchemy 2.0 ORM) • Parameterized Queries        │
│     Chronological Statutory AuditLog • Zero Secret Exposure                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete Project Structure

```
drishti/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                    # Auth dependencies & RBAC guards
│   │   │   └── v1/
│   │   │       ├── router.py              # Main API v1 router aggregation
│   │   │       └── endpoints/
│   │   │           ├── auth.py            # Login, logout, profile endpoints
│   │   │           └── cases.py           # Cases, OCR, analysis, review, reports
│   │   ├── core/
│   │   │   ├── config.py                  # Pydantic Settings & environment schemas
│   │   │   ├── errors.py                  # RFC 7807 error envelopes
│   │   │   ├── rate_limit.py              # In-memory sliding window rate limiter
│   │   │   ├── security.py                # Bcrypt password hashing & JWT handling
│   │   │   └── storage.py                 # File uploads, MIME check, SHA-256 hashes
│   │   ├── database/
│   │   │   ├── session.py                 # Async engine & session pooling
│   │   │   └── seed.py                    # Authority officer & case seeders
│   │   ├── models/
│   │   │   ├── base.py                    # DeclarativeBase, UUIDs, Timestamp mixins
│   │   │   ├── user.py                    # User credentials, roles, badges
│   │   │   ├── product.py                 # Products, sources, images, OCR entities
│   │   │   ├── analysis.py                # AnalysisResult, Findings, RiskAssessment
│   │   │   └── case.py                    # Cases, CaseReview, AuditLog
│   │   ├── schemas/
│   │   │   ├── auth.py                    # Login & token schemas
│   │   │   ├── case.py                    # Case, reviews, queue, audit trail schemas
│   │   │   ├── dashboard.py               # Dashboard metrics & telemetry schemas
│   │   │   ├── submission.py              # Product submission & image response schemas
│   │   │   ├── ocr.py                     # OCR result schemas & quality assessment
│   │   │   ├── intelligence.py            # Structured canonical product schemas
│   │   │   ├── deep_analysis.py           # Deep modular analysis schemas
│   │   │   ├── consistency.py             # Cross-source consistency schemas
│   │   │   ├── risk.py                    # Risk engine scoring & factors schemas
│   │   │   ├── explanation.py             # Traceable explainability schemas
│   │   │   ├── evidence_package.py        # Evidence package & integrity schemas
│   │   │   └── report.py                  # 8-section compliance report schemas
│   │   ├── services/
│   │   │   ├── ocr/                       # Image preprocessing & OCR service
│   │   │   ├── intelligence/              # Normalizer, ingredient parser, deduplicator
│   │   │   ├── deep_analysis/             # 5 modular regulatory analyzers
│   │   │   ├── consistency/               # Cross-source comparative engine
│   │   │   ├── risk/                      # Multi-factor statutory risk scorer
│   │   │   ├── explainability/            # Legal citations & verbatim finding mapper
│   │   │   ├── evidence/                  # Evidence package aggregator & hash verifier
│   │   │   └── reporting/                 # Report data builder, HTML & PDF generators
│   │   └── main.py                        # FastAPI application factory & lifecycle
│   ├── requirements.txt                   # Backend dependencies
│   └── tests/                             # 15 automated test suites (99 tests)
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                     # App layout with Authority Navbar & Footer
│   │   ├── page.tsx                       # Redirect & landing coordinator
│   │   ├── login/page.tsx                 # Official Authority Login portal
│   │   ├── dashboard/
│   │   │   ├── page.tsx                   # Main Surveillance Dashboard
│   │   │   ├── submit/page.tsx            # Multi-Modal Product Submission Portal
│   │   │   ├── priority/page.tsx          # Priority Review Queue (Search, Filter, Sort)
│   │   │   ├── cases/page.tsx             # Case Directory & Statutory Filter
│   │   │   ├── cases/[caseId]/analysis/   # Deep Regulatory Analysis Console
│   │   │   ├── cases/[caseId]/evidence/   # Evidence Viewer & Chain of Custody
│   │   │   ├── reports/page.tsx           # Compliance Report Dossier Center
│   │   │   └── profile/page.tsx           # Officer Profile & Credential Ledger
│   ├── components/                        # UI Components, Badges, Status pills
│   ├── lib/                               # API callers, auth state, formatting helpers
│   ├── types/                             # TypeScript models and interfaces
│   └── package.json                       # Next.js 16 dependencies
│
├── docs/                                  # Architectural & Statutory Documentation
│   ├── PROJECT_OVERVIEW.md                # Regulatory background, personas, statutory mandate
│   ├── SYSTEM_ARCHITECTURE.md             # Clean architecture, DB models, module boundaries
│   ├── DATA_FLOW.md                       # Sequence diagrams & data lifecycles
│   ├── API_ARCHITECTURE.md                # REST endpoints and request/response contracts
│   ├── AI_PIPELINE.md                     # Vision, OCR, structuring, and risk algorithms
│   ├── SECURITY.md                        # Authentication, RBAC, input safety, audit logging
│   ├── TESTING.md                         # Comprehensive test strategy & execution guide
│   ├── DEPLOYMENT.md                      # Production deployment & infrastructure runbook
│   └── FINAL_SYSTEM_OVERVIEW.md           # This document
│
├── docker/
│   ├── docker-compose.yml                 # Local & staging container orchestration
│   ├── Dockerfile.backend                 # Production FastAPI container
│   └── Dockerfile.frontend                # Production Next.js container
└── README.md                              # Repository overview and quickstart guide
```

---

## 4. All Implemented Features (Phases 1–17)

1. **Phase 1: Project Initialization & Infrastructure**: Async FastAPI, Next.js 16 (Turbopack), PostgreSQL 16 connection pooling, Docker Compose.
2. **Phase 2: Database Schema & Regulatory Data Models**: SQLAlchemy 2.0 ORM models covering Products, Sources, Images, Cases, Reviews, and Audit Logs.
3. **Phase 3: Secure Authentication & Session Security**: Bcrypt cost factor 12, cryptographic JWT with `drishti.gov.in` issuer, inactive account lockouts.
4. **Phase 4: Regulatory Dashboard & Metrics Telemetry**: Live surveillance metrics, risk distribution counters, priority queue counts.
5. **Phase 5: Multi-Modal Ingestion Gateway**: Ingestion via e-commerce URLs, physical packaging images, or text descriptions with SHA-256 image hashing.
6. **Phase 6: Image Preprocessing & Multi-Zone OCR**: Image normalization, Otsu binarization, multi-zone text detection (FOP/BOP, Nutrition, License).
7. **Phase 7: Product Information Structuring**: Normalization, ingredient parser, INS additive extraction, allergen identification, deduplication.
8. **Phase 8: Deep Regulatory Analysis**: 5-dimension analysis (License, Ingredients, Prohibited Claims, Packaging labeling, Manufacturer details).
9. **Phase 9: Cross-Source Consistency Reconciliation**: Matrix cross-referencing e-commerce claims vs physical pack OCR vs FoSCoS registry.
10. **Phase 10: Multi-Factor Risk Intelligence Engine**: Mathematical multi-factor risk scoring, 4-tier risk classification, data completeness ratio.
11. **Phase 11: Traceable Regulatory Explainability**: Verbatim finding trees, statutory legal section citations, "Why Flagged" plain-language summaries.
12. **Phase 12: Chain of Custody & Evidence Packaging**: Immutable evidence packages, SHA-256 digest validation, strict segregation of AI analysis notes.
13. **Phase 13: Evidence Viewer & Inspection Console**: UI evidence visualizer linking findings backwards to source URLs and packaging photos.
14. **Phase 14: Priority Review Queue & Case Management**: Dynamic priority triage queue with multi-field search, filtering, and officer review actions (Section 32 notices).
15. **Phase 15: Evidence-Backed Compliance Report Generation**: Structured 8-section compliance model, styled HTML briefs, signed binary PDF compilation via ReportLab.
16. **Phase 16: Security, Access Control & Auditability Architecture**: Role-based access control, 15MB file caps, sliding-window rate limiting (HTTP 429), chronological audit trail.
17. **Phase 17: Final Integration, Testing & Production Readiness Review**: Full 13-stage end-to-end integration test suite, 99/99 passing tests, complete operational documentation.

---

## 5. Known Limitations

1. **OCR Performance on Degraded Labels**: Severely torn, crumpled, or reflective holographic packaging labels may produce lower confidence OCR text. The system detects low quality and issues an explicit `LOW_QUALITY_WARNING`.
2. **In-Memory Rate Limiting**: The current sliding-window rate limiter runs in-memory within the ASGI process. In a distributed multi-node deployment behind a load balancer, a Redis-backed token bucket is recommended.
3. **External Registry Synchronization**: External FoSCoS registry lookups currently rely on local mock datasets and structured rules; real-time integration requires a direct government API gateway handshake.

---

## 6. Future Improvements & Roadmap

1. **Distributed Celery / Redis Workers**: Offload heavy OCR image processing and PDF compilation to asynchronous background queue workers.
2. **Batch Ingestion Pipeline**: Ingest hundreds of e-commerce listings simultaneously via CSV or automated marketplace scrapers.
3. **Digital Signature Integration (e-Sign / DSC)**: Implement cryptographic X.509 PKI certificate digital signing directly into generated PDF enforcement dossiers.
4. **Active Marketplace Takedown APIs**: Automated notification gateways sending Section 32 notices directly to verified e-commerce grievance officers.
