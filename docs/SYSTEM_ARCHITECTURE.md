# DRISHTI: System Architecture Specification
## Phase 0: Technical Architecture & System Decomposition

---

### 1. Architectural Philosophy & Design Principles

DRISHTI is architected as an **Asynchronous, Event-Driven Modular Monolith** designed for high throughput, strict domain isolation, and horizontal scalability, with a clear evolutionary path to microservices as regulatory workloads scale.

```
+---------------------------------------------------------------------------------------------------+
|                                      DRISHTI HIGH-LEVEL ARCHITECTURE                              |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ Authority Users / Field Officers ]         [ External Ingestion Sources ]                      |
|       |                     |                      |                     |                        |
|  ( Web Portal )       ( Mobile PWA )          ( E-Commerce Scraper ) ( Bulk CSV / API Feeds )     |
|       |                     |                      |                     |                        |
|       +----------+----------+                      +----------+----------+                        |
|                  |                                            |                                   |
|                  v                                            v                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |                           API GATEWAY / REVERSE PROXY (Nginx / Envoy)                       |  |
|  |             - SSL/TLS Termination  - Rate Limiting  - WAF  - JWT Validation                 |  |
|  +----------------------------------------------+----------------------------------------------+  |
|                                                 |                                                 |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  |                               DRISHTI CORE BACKEND (FastAPI Async)                          |  |
|  |  +------------------------+  +------------------------+  +-------------------------------+  |  |
|  |  | Auth & RBAC Service    |  | Ingestion Orchestrator |  | Case & Workflow Engine        |  |  |
|  |  +------------------------+  +------------------------+  +-------------------------------+  |  |
|  |  +------------------------+  +------------------------+  +-------------------------------+  |  |
|  |  | Audit & Lineage Engine |  | Dossier Generator (PDF)|  | FoSCoS Registry Adapter       |  |  |
|  |  +------------------------+  +------------------------+  +-------------------------------+  |  |
|  +----------------------------------------------+----------------------------------------------+  |
|                                                 |                                                 |
|                        Asynchronous Event Bus / Task Broker (Redis / Celery / RabbitMQ)           |
|                                                 |                                                 |
|         +-----------------------+---------------+---------------+-----------------------+         |
|         |                       |                               |                       |         |
|         v                       v                               v                       v         |
|  +---------------+     +------------------+           +-------------------+    +---------------+  |
|  | WORKER POOL 1 |     |  WORKER POOL 2   |           |   WORKER POOL 3   |    | WORKER POOL 4 |  |
|  | Web Scraper & |     | Vision, Dewarp & |           | Regulatory NLP &  |    | Risk Scoring &|  |
|  | DOM Extractor |     | Multi-Zone OCR   |           | Rule Engines      |    | Consistency   |  |
|  +---------------+     +------------------+           +-------------------+    +---------------+  |
|         |                       |                               |                       |         |
|         +-----------------------+---------------+---------------+-----------------------+         |
|                                                 |                                                 |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  |                                     PERSISTENCE & STORAGE TIER                              |  |
|  |  +--------------------+  +----------------------+  +---------------------+  +------------+  |  |
|  |  | PostgreSQL 16      |  | pgvector Ext.        |  | Redis 7             |  | MinIO / S3 |  |  |
|  |  | - Relational Data  |  | - Regulatory Clause  |  | - Distributed Cache |  | - Raw Images|  | |
|  |  | - JSONB Schemas    |  |   Embeddings         |  | - Session State     |  | - PDF Dossiers |
|  |  | - Case Audit Logs  |  | - Claim Vectors      |  | - Task Rate Limits  |  | - Zone Crops|  | |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

#### Core Architectural Decisions (ADRs)
1. **Clean / Onion Architecture**: Strict separation of Domain entities, Application use cases, Interface adapters, and Infrastructure layers. The business rules of food compliance must remain independent of frameworks, UI, or database drivers.
2. **Asynchronous Non-Blocking Processing**: Web scraping, image dewarping, high-resolution OCR, and LLM reasoning are compute-intensive. All long-running tasks are dispatched asynchronously through a distributed queue, returning an immediate Job ID to the caller with WebSocket / SSE progress tracking.
3. **Immutability of Evidence**: Raw ingested images, scraped HTML snapshots, and finalized dossiers are immutable. Once written to object storage (MinIO/S3), their SHA-256 hash is signed and recorded in PostgreSQL for legal chain of custody.
4. **Hybrid Rule Execution (Deterministic + Probabilistic)**: Pure AI/LLMs alone are prone to non-deterministic variation. DRISHTI uses strict deterministic mathematical & syntax rule engines for hard legislative requirements (dates, RDA percentages, additive limits, license checksums) and reserves calibrated LLM reasoning for nuanced natural language claim evaluation with mandatory grounding.

---

### 2. Frontend Architecture

The DRISHTI frontend is designed for high-density, mission-critical regulatory oversight. It combines intuitive desktop workstation layouts for deep investigative analysis with responsive mobile-optimized views for field inspections.

```
+----------------------------------------------------------------------------------------+
|                                  FRONTEND ARCHITECTURE                                 |
+----------------------------------------------------------------------------------------+
|  Framework: Next.js 14+ (App Router) / React 19 / TypeScript Strict Mode               |
|  Styling: Vanilla CSS Design System with CSS Tokens (CSS Modules / Tailwind-free)      |
|  State Management: Zustand (Client state) + TanStack Query v5 (Server cache & polling) |
+----------------------------------------------------------------------------------------+
                                            |
        +-----------------------------------+-----------------------------------+
        |                                                                       |
        v                                                                       v
+-----------------------------+                         +-----------------------------+
|    AUTHORITY DESKTOP SUITE  |                         |     FIELD INSPECTION PWA    |
| - High-throughput triage    |                         | - Camera barcode/FSSAI scan |
| - Split-screen inspector    |                         | - Quick image batch upload  |
| - Interactive label canvas  |                         | - Offline-first caching     |
| - Dossier PDF previewer     |                         | - Immediate risk badge      |
+-----------------------------+                         +-----------------------------+
        |                                                                       |
        +-----------------------------------+-----------------------------------+
                                            |
                                            v
+----------------------------------------------------------------------------------------+
|                             CORE FRONTEND COMPONENT MODULES                            |
|                                                                                        |
|  1. IngestionModule:       URL submitter, drag-and-drop multi-image pack uploader     |
|  2. TriageDashboard:       Priority matrix, risk heatmap, district-level filtering     |
|  3. InspectionCanvas:      Interactive OpenSeadragon/HTML5 canvas with bounding-box    |
|                            overlays, OCR text inspector, zone zoom, crop verification  |
|  4. DiscrepancyComparison: Three-column differential view:                            |
|                            [ E-Comm Claim ] vs [ Packaging Label ] vs [ FoSCoS Lic ]   |
|  5. ComplianceReasonTree:  Interactive tree rendering of statutory rules evaluated    |
|  6. DossierViewer:         PDF/A renderer with digital signature status verification  |
+----------------------------------------------------------------------------------------+
```

#### Frontend Key Architectural Characteristics:
- **Interactive Inspection Canvas**: Custom canvas engine rendering high-resolution packaging images with SVG/Canvas overlays representing identified zones (Ingredients, Nutrition Table, Veg Logo, FSSAI Stamp). Clicking any zone instantly synchronizes with the extracted text table and associated compliance findings.
- **Optimistic UI with Real-Time Updates**: Uses Server-Sent Events (SSE) / WebSockets to stream pipeline stage completions (e.g., *[Ingestion 100%] -> [OCR 100%] -> [Rules 80%] -> [Risk Scoring Complete]*).
- **Zero Heavy Bundle Bloat**: Avoids heavy generic UI component libraries; relies on a hand-crafted, high-performance CSS Token design system optimized for crisp data tables, high-contrast regulatory status badges, and sub-second load times.

---

### 3. Backend Architecture

The backend is built around **Python 3.11+ and FastAPI**, leveraging Python's native async I/O alongside its dominant ecosystem for computer vision (OpenCV, PyTorch) and NLP/LLM orchestration (LangChain/LlamaIndex/DSPy).

```
backend/
├── app/
│   ├── core/                  # Configuration, logging, security, telemetry
│   ├── domain/                # Enterprise Business Entities & Value Objects (Pydantic/Dataclasses)
│   │   ├── product.py         # Canonical Product Model
│   │   ├── compliance.py      # Rule results, violations, severity definitions
│   │   ├── dossier.py         # Evidence Dossier structure
│   │   └── case.py            # Regulatory inspection case lifecycle
│   ├── services/              # Application Use-Case Logic (Pure Business Flow)
│   │   ├── ingestion/         # URL scraping, image validation
│   │   ├── ocr_orchestrator/  # Image preprocessing, zone routing, OCR merging
│   │   ├── compliance_engine/ # Rule execution, claim evaluation
│   │   ├── discrepancy_engine/# Cross-source comparison algorithms
│   │   ├── risk_scorer/       # Multi-factor mathematical scoring
│   │   └── dossier_service/   # Cryptographic PDF/A generation
│   ├── adapters/              # Secondary/Driven Ports (External I/O)
│   │   ├── db/                # SQLAlchemy 2.0 Async ORM repositories
│   │   ├── storage/           # S3 / MinIO client adapter
│   │   ├── foscos/            # FSSAI FoSCoS registry integration adapter
│   │   └── llm/               # LLM client adapters with structured output guarantees
│   └── api/                   # Primary/Driving Adapters (HTTP / WebSockets)
│       └── v1/                # Versioned REST endpoints
```

#### Key Backend Design Patterns:
1. **Repository Pattern with Async SQLAlchemy 2.0**: Abstracting all database persistence operations behind clean repository interfaces, decoupling domain models from database schemas.
2. **Worker Pool Isolation**: Decoupled task queues ensure that long-running GPU-bound OCR or LLM jobs do not starve I/O-bound web-scraping or REST API requests.
3. **Circuit Breakers & Retries**: External integrations (such as FoSCoS portal lookups and e-commerce scraping targets) are wrapped with Tenacity/Resilience4j style circuit breakers to handle rate-limiting and intermittent outages gracefully.

---

### 4. Database Architecture & Entity Relationships

DRISHTI utilizes **PostgreSQL 16** as the unified transactional and vector persistence layer, combined with **Redis 7** for ephemeral caching and **MinIO/S3** for blob storage.

```
+---------------------------------------------------------------------------------------------------+
|                                     ENTITY RELATIONSHIP MODEL                                     |
+---------------------------------------------------------------------------------------------------+

 +--------------------+            1:N            +---------------------+
 |      Products      |<--------------------------|   ProductArtifacts  |
 |--------------------|                           |---------------------|
 | id (UUID, PK)      |                           | id (UUID, PK)       |
 | canonical_name     |                           | product_id (FK)     |
 | brand_name         |                           | artifact_type       | (FOP_IMAGE, BOP_IMAGE,
 | declared_category  |                           | storage_uri         |  WEB_HTML, RAW_DESC)
 | fssai_license_no   |                           | sha256_hash         |
 | source_channel     |                           | image_metadata      | (Resolution, EXIF)
 | created_at         |                           +---------------------+
 +--------------------+                                      |
          | 1                                                | 1:N
          |                                                  v
          | 1:N                                   +---------------------+
          |                                       |    ExtractionRuns   |
          v                                       |---------------------|
 +--------------------+                           | id (UUID, PK)       |
 | CanonicalNutrients |                           | artifact_id (FK)    |
 |--------------------|                           | ocr_engine_version  |
 | id (UUID, PK)      |                           | raw_extracted_text  |
 | product_id (FK)    |                           | detected_zones_json |
 | nutrient_name      |                           | status, latency_ms  |
 | value_per_100g     |                           +---------------------+
 | value_per_serve    |                                      |
 | unit (g, mg, mcg)  |                                      | 1:N
 +--------------------+                                      v
          |                                       +---------------------+
          |                                       |   ExtractedZones    |
          | 1:N                                   |---------------------|
          v                                       | id (UUID, PK)       |
 +--------------------+                           | extraction_run_id   |
 | ProductIngredients |                           | zone_type           | (INGREDIENTS, NUTRITION,
 |--------------------|                           | bbox_coordinates    |  VEG_LOGO, FSSAI_LIC)
 | id (UUID, PK)      |                           | crop_storage_uri    |
 | product_id (FK)    |                           | confidence_score    |
 | raw_text           |                           | parsed_json         |
 | normalized_name    |                           +---------------------+
 | ins_number         |
 | is_additive        |
 | is_allergen        |
 +--------------------+
          |
          | 1:N
          v
 +--------------------+            1:N            +---------------------+
 | ComplianceFindings |<--------------------------|  EvidenceDossiers   |
 |--------------------|                           |---------------------|
 | id (UUID, PK)      |                           | id (UUID, PK)       |
 | product_id (FK)    |                           | product_id (FK)     |
 | rule_code          | (e.g. FSSAI-ADV-2018-R4)  | dossier_version     |
 | severity_tier      | (CRITICAL, HIGH, MED, LOW)| pdf_storage_uri     |
 | statutory_clause   |                           | dossier_hash_sha256 |
 | violation_details  |                           | digital_signature   |
 | discrepancy_source |                           | generated_at        |
 | evidence_zone_id   |                           +---------------------+
 +--------------------+                                      |
          |                                                  | 1:1
          | 1:1                                              v
          v                                       +---------------------+
 +--------------------+                           |   RegulatoryCases   |
 |  ProductRiskScores |                           |---------------------|
 |--------------------|                           | id (UUID, PK)       |
 | id (UUID, PK)      |                           | product_id (FK)     |
 | product_id (FK)    |                           | dossier_id (FK)     |
 | composite_score    | (0.0 to 100.0)            | case_number (Unique)|
 | health_hazard_score|                           | status              | (TRIAGED, ASSIGNED,
 | deception_score    |                           | assigned_fso_id     |  NOTICE_ISSUED, CLOSED)
 | license_risk_score |                           | district_code       |
 | risk_tier          |                           | created_at          |
 +--------------------+                           +---------------------+
```

---

### 5. Module Boundaries and Interface Contracts

DRISHTI enforces strict boundaries between its seven major logical subsystems:

```
[ Ingestion Subsystem ]
        │  Produces: RawArtifactEvent (URI, Hash, SourceType)
        ▼
[ Vision & OCR Subsystem ]
        │  Produces: OCRCompletedEvent (DetectedZones, ExtractedTokens, NormalizedCrops)
        ▼
[ Entity Extraction & Normalization Subsystem ]
        │  Produces: CanonicalProductSpec (NutritionTable, IngredientsList, ClaimsList)
        ▼
[ Regulatory Compliance & Discrepancy Subsystem ]
        │  Produces: ComplianceEvaluationEvent (ViolationsList, DiscrepanciesList)
        ▼
[ Risk Intelligence Engine ]
        │  Produces: RiskProfile (CompositeScore, RiskTier, PriorityRank)
        ▼
[ Evidence & Dossier Subsystem ]
        │  Produces: DossierGeneratedEvent (CertifiedPDF_URI, SHA256)
        ▼
[ Case & Workflow Subsystem ]
           Enables: FSO Review, Assignment, Enforcement Actions
```

#### Decoupling Guarantees:
- **No Direct Subsystem Database Coupling**: Modules communicate via typed DTO contracts and asynchronous message payloads.
- **Pluggable OCR & Vision Engines**: The OCR Subsystem implements an `IOCREngine` interface, allowing hot-swapping between local models (PaddleOCR, Tesseract, TrOCR) and specialized cloud APIs without altering downstream extraction logic.
- **Pluggable Regulatory Rulesets**: Rules are codified as independent declarative modules implementing `IRegulatoryRule`. Adding a new FSSAI amendment (e.g., 2024 Labelling Revision) requires only adding a new Rule class without modifying the engine core.

---

### 6. Security, Compliance, and Data Protection Architecture

1. **Authentication & Role-Based Access Control (RBAC)**:
   - Built on OAuth2 with PKCE and JWT tokens.
   - Distinct roles: `SUPER_ADMIN`, `CENTRAL_ANALYST`, `DESIGNATED_OFFICER`, `FOOD_SAFETY_OFFICER`, `LEGAL_AUDITOR`.
   - Granular state-level and district-level multi-tenancy: an FSO from Bengaluru Urban cannot alter or view confidential inspection files of New Delhi District unless delegated.
2. **Data Integrity & Cryptographic Chain of Custody**:
   - Every uploaded image has its SHA-256 hash computed immediately at the API Gateway edge.
   - Any generated Dossier PDF embeds:
     - The raw SHA-256 hashes of all input evidence artifacts.
     - Timestamp of extraction from a secure Network Time Protocol (NTP) source.
     - System digital signature preventing tampering.
3. **Data Protection & Encryption**:
   - All REST and WebSocket communications enforced over TLS 1.3.
   - S3/MinIO storage encrypted at rest using AES-256.
   - Database field-level encryption for sensitive inspector remarks and confidential informant disclosures.

---

### 7. Reliability, Scalability, and Fault Tolerance

- **Rate-Limiting & Scraping Backoff**: Exponential backoff and rotating proxy adapters ensure compliance with website robots.txt and prevent IP blocking during automated surveillance.
- **Dead Letter Queues (DLQ)**: Images that fail OCR due to severe corruption or unreadable blur are routed to a DLQ with a diagnostic flag (`IMAGE_QUALITY_INSUFFICIENT`) for manual FSO review rather than blocking the worker queue.
- **Stateless Application Servers**: All FastAPI application instances are completely stateless, allowing effortless auto-scaling behind the API Gateway based on CPU/Memory thresholds.
