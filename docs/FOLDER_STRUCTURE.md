# DRISHTI: Proposed Repository Folder Structure
## Phase 0: Project Layout, Modular Boundaries & Component Hierarchy

---

### 1. Architectural Principles of the Repository Structure

The DRISHTI codebase is organized as an **Enterprise Modular Monorepo** designed to keep domain logic decoupled from external infrastructure, frameworks, and third-party AI dependencies:

1. **Separation of Concerns**: Core business logic (FSSAI statutory rules, risk mathematics, canonical product models) lives in `backend/app/domain` and `ai_pipeline/rules`, completely isolated from HTTP frameworks (FastAPI) or database drivers (SQLAlchemy).
2. **Modular AI Pipeline**: Computer vision models, OCR inference scripts, and LLM reasoning modules reside in `ai_pipeline/`, allowing dedicated machine learning engineers to test and benchmark models independently of web APIs.
3. **Shared Contracts**: Common data schemas and DTOs in `packages/contracts/` provide a single source of truth across backend services and frontend clients.
4. **Isolated Regulatory Knowledge Base**: Statutory gazette notifications, ICMR-NIN RDA tables, INS additive databases, and FoSCoS category mappings reside in `knowledge_base/` as structured JSON, YAML, and vector embeddings.

---

### 2. Complete Repository Directory Tree

```text
drishti/
├── .github/                               # CI/CD workflows, issue templates, PR linters
│   └── workflows/
│       ├── backend-ci.yml                 # Lint, unit tests, coverage for FastAPI
│       ├── frontend-ci.yml                # Typecheck, lint, build for Next.js
│       └── ai-eval-benchmark.yml          # Automated regression evaluation on Golden Dataset
│
├── docs/                                  # Architectural documentation & statutory references
│   ├── PROJECT_OVERVIEW.md                # Strategic context, regulatory scope, personas
│   ├── SYSTEM_ARCHITECTURE.md             # System decomposition, Hexagonal design, DB models
│   ├── DATA_FLOW.md                       # Sequence diagrams, DTOs, state machine
│   ├── API_ARCHITECTURE.md                # REST, SSE, WebSocket endpoint specifications
│   ├── AI_PIPELINE.md                     # Vision, OCR, NLP, Hybrid reasoning, Risk scoring
│   ├── DEVELOPMENT_ROADMAP.md             # Engineering phases, milestones, risk matrix
│   └── FOLDER_STRUCTURE.md                # This comprehensive folder layout specification
│
├── packages/
│   └── contracts/                         # Shared Pydantic schemas & TypeScript type definitions
│       ├── src/
│       │   ├── product.json               # Canonical product specification schema
│       │   ├── compliance.json            # Regulatory rule violation schemas
│       │   ├── discrepancy.json           # Cross-source discrepancy matrix schema
│       │   ├── risk.json                  # Risk score & tier schemas
│       │   └── dossier.json               # Evidence dossier structure schema
│       └── package.json
│
├── backend/                               # Core Application Backend (Python 3.11+ / FastAPI)
│   ├── app/
│   │   ├── core/                          # Cross-cutting foundational utilities
│   │   │   ├── config.py                  # Pydantic BaseSettings (DB, S3, Redis, JWT)
│   │   │   ├── security.py                # JWT creation, password hashing, RBAC decorators
│   │   │   ├── logging.py                 # Structured JSON logger with Trace IDs
│   │   │   └── exceptions.py              # Custom domain exceptions & RFC 7807 handlers
│   │   │
│   │   ├── domain/                        # Pure Domain Entities & Value Objects (DDD)
│   │   │   ├── models/
│   │   │   │   ├── product.py             # Product entity & CanonicalProductSpecification
│   │   │   │   ├── artifact.py            # Uploaded images & scraped DOM artifacts
│   │   │   │   ├── compliance.py          # ComplianceFinding, Severity, RuleReference
│   │   │   │   ├── discrepancy.py         # CrossSourceDiscrepancy entity
│   │   │   │   ├── risk.py                # ProductRiskScore, Tier, DimensionScores
│   │   │   │   ├── dossier.py             # EvidenceDossier, SHA256Seal
│   │   │   │   └── case.py                # RegulatoryCase, CaseStatus, AuditLog
│   │   │   └── interfaces/                # Ports (Abstract interfaces for repositories & adapters)
│   │   │       ├── repositories.py        # IProductRepository, ICaseRepository, etc.
│   │   │       ├── storage_port.py        # IObjectStorageService
│   │   │       └── foscos_port.py         # IFoscosRegistryService
│   │   │
│   │   ├── services/                      # Application Use-Cases & Orchestration
│   │   │   ├── ingestion/
│   │   │   │   ├── url_service.py         # URL submission & job scheduling
│   │   │   │   └── media_service.py       # Image validation, hashing, storage upload
│   │   │   ├── extraction/
│   │   │   │   └── extraction_service.py  # Orchestrating vision & OCR extraction tasks
│   │   │   ├── compliance/
│   │   │   │   └── compliance_service.py  # Rule execution & violation aggregation
│   │   │   ├── discrepancy/
│   │   │   │   └── discrepancy_service.py # 3-way alignment (Web vs Pack vs FoSCoS)
│   │   │   ├── risk/
│   │   │   │   └── risk_service.py        # Multi-factor score computation
│   │   │   ├── dossier/
│   │   │   │   └── dossier_service.py     # PDF/A compilation & cryptographic signing
│   │   │   └── case/
│   │   │       └── case_service.py        # Case lifecycle, triage, FSO assignment
│   │   │
│   │   ├── adapters/                      # Secondary / Driven Adapters (External Systems)
│   │   │   ├── db/                        # PostgreSQL implementation via SQLAlchemy
│   │   │   │   ├── base.py                # Async engine & DeclarativeBase
│   │   │   │   ├── models.py              # SQLAlchemy ORM table definitions
│   │   │   │   ├── migrations/            # Alembic database migration scripts
│   │   │   │   └── repositories/          # Concrete SQLAlchemy repositories
│   │   │   ├── storage/
│   │   │   │   └── s3_adapter.py          # MinIO / AWS S3 async client adapter
│   │   │   └── foscos/
│   │   │       └── foscos_client.py       # FoSCoS registry scraping / API client
│   │   │
│   │   ├── api/                           # Primary / Driving Adapters (FastAPI HTTP & WS)
│   │   │   ├── v1/
│   │   │   │   ├── router.py              # Root API v1 router
│   │   │   │   ├── auth.py                # /auth endpoints (login, token, refresh)
│   │   │   │   ├── products.py            # /products endpoints (ingest, metadata)
│   │   │   │   ├── extraction.py          # /extraction endpoints (zones, OCR)
│   │   │   │   ├── compliance.py          # /compliance endpoints (rule results)
│   │   │   │   ├── discrepancies.py       # /discrepancies endpoints (diff matrix)
│   │   │   │   ├── risk.py                # /risk endpoints (scores, queue)
│   │   │   │   ├── dossiers.py            # /dossiers endpoints (export, PDF)
│   │   │   │   ├── cases.py               # /cases endpoints (workflow, actions)
│   │   │   │   └── admin.py               # /admin endpoints (rules, audit)
│   │   │   └── dependencies.py            # FastAPI dependency injections (DB session, Auth)
│   │   │
│   │   └── workers/                       # Asynchronous Task Queue Workers (Celery)
│   │       ├── celery_app.py              # Celery configuration & broker connection
│   │       ├── tasks_scraper.py           # Web scraping background tasks
│   │       ├── tasks_vision.py            # Vision & OCR task delegation
│   │       ├── tasks_compliance.py        # Rule engine evaluation tasks
│   │       └── tasks_dossier.py           # Background PDF generation tasks
│   │
│   ├── tests/                             # Backend Test Suite
│   │   ├── unit/                          # Isolated unit tests for domain & services
│   │   ├── integration/                   # DB, S3, API route integration tests
│   │   └── conftest.py                    # Pytest fixtures & async test database setup
│   │
│   ├── pyproject.toml                     # Poetry / pip build configuration & dependencies
│   ├── Dockerfile                         # Production multi-stage Dockerfile
│   └── alembic.ini                        # Database migration configuration
│
├── ai_pipeline/                           # Computer Vision, OCR & Machine Learning Engine
│   ├── vision/                            # Image preprocessing & geometric rectification
│   │   ├── dewarping.py                   # 3D cylindrical surface unwarping & TPS
│   │   ├── enhancement.py                 # Glare suppression, CLAHE, super-resolution
│   │   └── zone_detector.py               # YOLOv8-Doc / LayoutLM zone bounding box model
│   │
│   ├── ocr/                               # Multi-Lingual Optical Character Recognition
│   │   ├── ocr_engine.py                  # Primary PaddleOCR v4 multi-lingual driver
│   │   ├── script_detector.py             # Script identifier (Latin, Devanagari, Dravidian)
│   │   └── vlm_fallback.py                # Vision-Language Model zero-shot fallback
│   │
│   ├── nlp/                               # Entity Normalization & Taxonomy Matching
│   │   ├── nutrition_parser.py            # Key-value extraction for nutritional tables
│   │   ├── ingredient_parser.py           # Sub-ingredient parser & allergen detector
│   │   ├── ins_resolver.py                # Food Chemicals / INS code lookup resolver
│   │   └── claim_extractor.py             # Front-of-pack marketing claim segmenter
│   │
│   ├── reasoning/                         # Neuro-Symbolic Compliance Verification
│   │   ├── rules/                         # Deterministic Regulatory Rules
│   │   │   ├── labelling_2020.py          # FSS (Labelling and Display) Regulations
│   │   │   ├── advertising_2018.py        # FSS (Advertising and Claims) Regulations
│   │   │   ├── additives_2011.py          # FSS (Food Products & Additives) Regulations
│   │   │   └── rda_limits_2022.py         # ICMR-NIN Tolerable Upper Limit checks
│   │   ├── rag/                           # Calibrated Semantic Reasoning (LLM)
│   │   │   ├── prompt_templates.py        # Zero-hallucination structured prompt schemas
│   │   │   ├── retriever.py               # Vector search over statutory gazettes
│   │   │   └── claim_validator.py         # LLM claim auditor with grounding checks
│   │   └── discrepancy/
│   │       └── consistency_checker.py     # Triangulation engine (Web vs Label vs FoSCoS)
│   │
│   ├── scoring/                           # Mathematical Risk Intelligence
│   │   ├── risk_calculator.py             # Composite formula calculation (H, D, L, M, V)
│   │   └── priority_ranker.py             # Dynamic triage priority sorting algorithm
│   │
│   ├── evaluation/                        # Evaluation & Benchmarking Harness
│   │   ├── golden_dataset/                # 200 ground-truth annotated packaging scans
│   │   └── evaluate_accuracy.py           # Automated evaluation script (CER, mAP, F1)
│   │
│   └── requirements-ai.txt                # PyTorch, PaddleOCR, OpenCV dependencies
│
├── knowledge_base/                        # Statutory Legal Reference Data & Taxonomies
│   ├── regulations/                       # Verbatim text of statutory gazettes (for RAG)
│   │   ├── fss_act_2006.md                # Food Safety and Standards Act, 2006
│   │   ├── labelling_display_2020.md      # FSS (Labelling and Display) Regulations, 2020
│   │   └── advertising_claims_2018.md     # FSS (Advertising and Claims) Regulations, 2018
│   ├── taxonomies/                        # Structured standard reference data
│   │   ├── ins_additives_db.json          # 400+ permitted/prohibited INS food additives
│   │   ├── icmr_nin_rda_2020.json         # Recommended Dietary Allowances per demographic
│   │   ├── allergens_registry.json        # Mandatory allergen declaration list
│   │   └── prohibited_adulterants.json    # Banned chemicals (Rhodamine B, Metanil Yellow)
│   └── embeddings/                        # Pre-generated vector embeddings for gazette search
│
├── frontend/                              # Authority Portal & Field Inspector Web App
│   ├── app/                               # Next.js 14+ App Router
│   │   ├── layout.tsx                     # Root layout with ThemeProvider & AuthProvider
│   │   ├── page.tsx                       # Redirect or public login page
│   │   ├── login/                         # Officer login & OTP authentication
│   │   ├── dashboard/                     # Executive & District Triage Dashboard
│   │   ├── products/                      # Product catalog & search
│   │   │   ├── page.tsx                   # Product listing & filter table
│   │   │   ├── [id]/                      # Detailed Product Inspector View
│   │   │   │   ├── page.tsx               # Master inspector layout
│   │   │   │   ├── canvas/                # Interactive packaging label zoom & crop canvas
│   │   │   │   ├── discrepancy/           # 3-way discrepancy differential view
│   │   │   │   └── dossier/               # Embedded PDF/A dossier viewer
│   │   │   └── ingest/                    # Product submission (URL + multi-image upload)
│   │   └── cases/                         # Authority workflow management
│   │       ├── page.tsx                   # Active enforcement cases & queue
│   │       └── [case_id]/                 # Case disposition, Section 32 notice issuance
│   │
│   ├── components/                        # Reusable Vanilla CSS Component System
│   │   ├── ui/                            # Atoms: Buttons, Badges, Modals, Spinners, Tables
│   │   ├── canvas/                        # OpenSeadragon / Canvas Bounding Box Renderer
│   │   ├── forms/                         # Multi-image uploader, URL input form
│   │   └── cards/                         # RiskScoreCard, DiscrepancyCard, FindingRow
│   │
│   ├── lib/                               # Core client-side utilities & HTTP clients
│   │   ├── api_client.ts                  # Fetch / Axios wrapper with token auto-refresh
│   │   ├── sse_client.ts                  # Server-Sent Events subscriber for progress
│   │   └── utils.ts                       # Date formatters, risk color mappings
│   │
│   ├── stores/                            # Lightweight Client State (Zustand)
│   │   ├── auth_store.ts                  # Current officer user, role, token
│   │   └── inspection_store.ts            # Active product, selected zone, zoom level
│   │
│   ├── styles/                            # Design System Tokens & Global CSS
│   │   ├── variables.css                  # CSS custom properties (colors, typography)
│   │   ├── globals.css                    # Base resets & accessibility styles
│   │   └── components/                    # Scoped component styles
│   │
│   ├── package.json                       # Next.js, React, TypeScript dependencies
│   ├── tsconfig.json                      # Strict TypeScript compiler options
│   └── next.config.mjs                    # Next.js configuration (asset domains, proxies)
│
├── infra/                                 # Infrastructure & Deployment Automation
│   ├── docker-compose.yml                 # Local dev orchestration (FastAPI, Next, PG, MinIO)
│   ├── docker-compose.prod.yml            # Production container configuration
│   ├── nginx/                             # Reverse proxy & SSL termination configuration
│   │   └── nginx.conf
│   ├── k8s/                               # Kubernetes manifests (StatefulSets, Deployments)
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   └── celery-workers-deployment.yaml
│   └── scripts/                           # Initialization & seed utilities
│       ├── seed_knowledge_base.py         # Ingest FSSAI gazette texts into pgvector
│       └── seed_demo_products.py          # Load synthetic test products & labels
│
└── README.md                              # Project landing page & quickstart guide
```

---

### 3. Guidelines for Modular Expansion

- **Adding a New E-Commerce Scraper**: Add a new scraper module under `backend/app/services/ingestion/` implementing `IEcommerceScraper`. Register the domain regex in `config.py`.
- **Codifying a New FSSAI Regulation**: Add an independent rule class under `ai_pipeline/reasoning/rules/` implementing `IRegulatoryRule`. Register the rule in `rules_registry.py`. Downstream compliance orchestrators will automatically execute the rule without modifying the core engine.
- **Integrating a New OCR Model**: Implement the `IOCREngine` interface under `ai_pipeline/ocr/`. Downstream zone detection and canonical normalizers will consume the output without code changes.
