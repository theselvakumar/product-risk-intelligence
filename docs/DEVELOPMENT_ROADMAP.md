# DRISHTI: Engineering Roadmap & Implementation Strategy
## Phase 0: Phased Delivery, Milestones, Dependencies & Risk Mitigation

---

### 1. Phased Engineering Delivery Plan

DRISHTI is organized into **six progressive engineering phases (Phases 0 through 5)** to manage technical complexity, guarantee milestone verifiability, and systematically mitigate high-risk dependencies:

```
[ Phase 0: Architecture & Foundation Planning ]  <-- CURRENT PHASE
  ├── System design, interface contracts, DTO schemas, regulatory baseline
  └── Output: Formal technical blueprints and project foundation
           │
           ▼
[ Phase 1: Core Platform & Ingestion Infrastructure ]
  ├── FastAPI scaffolding, PostgreSQL 16 + pgvector, MinIO S3 storage, Redis
  ├── Asynchronous Celery / Redis task queue pipeline
  ├── Headless e-commerce scrapers (Playwright) & multi-image upload gateway
  └── Next.js 14+ frontend shell & design system foundation
           │
           ▼
[ Phase 2: Computer Vision, Label Dewarping & Multi-Zone OCR ]
  ├── Image preprocessing (Cylinder dewarping, glare suppression, CLAHE)
  ├── YOLOv8-Doc / LayoutLM zone segmentation (Nutrition, Ingredients, Logos, Dates)
  ├── PaddleOCR v4 / TrOCR multi-lingual text extraction (English, Hindi, Regional)
  └── Canonical entity parser (Nutritional facts, INS additive resolution)
           │
           ▼
[ Phase 3: Regulatory Reasoning Engine & Cross-Source Consistency ]
  ├── Deterministic FSSAI Rule Engine (Labelling 2020, Additives 2011, RDA 2022)
  ├── Calibrated LLM Claim Verification (Advertising 2018, zero-hallucination RAG)
  ├── FoSCoS registry verification adapter (14-digit checksum & category lookup)
  └── 3-Way Cross-Source Discrepancy Matrix (Web vs. Label vs. FoSCoS)
           │
           ▼
[ Phase 4: Risk Intelligence Engine & Evidence Dossier Generation ]
  ├── Multi-factor composite risk scoring algorithm (0-100 scale, risk tiers)
  ├── Automated Priority Triage queue generation for enforcement authorities
  ├── Cryptographic Evidence Dossier generator (PDF/A, SHA-256 tamper seals)
  └── Interactive inspection canvas (visual bounding box sync)
           │
           ▼
[ Phase 5: Authority Workflow, Pilot Testing & Hardening ]
  ├── Role-based enforcement workflow (FSO field sampling, DO Section 32 notices)
  ├── Real-world pilot testing against 1,000 real e-commerce & retail SKUs
  ├── Security hardening, penetration testing, and load optimization
  └── Final deployment on sovereign cloud infrastructure
```

---

### 2. Milestone Deliverables & Acceptance Criteria

| Phase | Milestone Name | Key Technical Deliverables | Strict Acceptance Criteria |
|---|---|---|---|
| **Phase 0** | Architecture & Specifications | Architecture blueprints, API contracts, Data flow schemas, AI pipeline design, Folder structure | 100% specification alignment, complete domain model definition, zero placeholder logic. |
| **Phase 1** | Ingestion & Storage Backbone | FastAPI core, DB migrations, S3/MinIO bucket configuration, Playwright scraper, Next.js portal base | Ingest valid product URL & multi-image batch in < 5s; SHA-256 calculated & stored in PostgreSQL. |
| **Phase 2** | Vision & OCR Extraction | Label unwarping, 8-zone segmentation, OCR extraction engine, Canonical Product Normalizer | Zone detection mAP > 90%; OCR CER < 3.5% on English, < 6% on Hindi; valid JSON extraction. |
| **Phase 3** | Compliance & Discrepancy | FSSAI ruleset engine, RAG claim evaluator, FoSCoS client, 3-way discrepancy detector | 100% deterministic accuracy on numeric limits; zero hallucinated violations; FoSCoS lookup < 1.5s. |
| **Phase 4** | Risk Scoring & Dossiers | Mathematical risk engine, automated PDF/A generator, OpenSeadragon canvas UI | Risk score generated in < 50ms; PDF/A dossier generated with valid SHA-256 seal & bounding boxes. |
| **Phase 5** | Authority Case Workflow | FSO/DO case management portal, audit logging, pilot benchmark evaluation | End-to-end case flow verified; pilot on 1,000 SKUs achieved > 92% precision against expert human audits. |

---

### 3. Comprehensive Technology Stack & Dependencies

#### 3.1 Backend & Core Platform
- **Python 3.11+ / FastAPI**: High-performance asynchronous REST API framework.
- **Pydantic v2**: High-speed data validation and strict contract serialization.
- **SQLAlchemy 2.0 (Asyncpg)**: Modern asynchronous ORM for PostgreSQL.
- **Celery 5.3+ with Redis 7**: Distributed task queue for asynchronous worker scheduling.
- **Playwright / BeautifulSoup4**: Headless browser automation for dynamic e-commerce rendering.
- **WeasyPrint / ReportLab**: Headless generation of statutory PDF/A compliance dossiers.

#### 3.2 AI, Computer Vision & NLP
- **PyTorch 2.2+ / torchvision**: Core deep learning inference framework.
- **OpenCV 4.9+**: Geometric transformations, perspective unwarping, bilateral glare filtering.
- **PaddleOCR v4 / HuggingFace TrOCR**: Multi-lingual optical character recognition.
- **Ultralytics YOLOv8 / LayoutLMv3**: Document layout analysis and statutory zone detection.
- **LangChain / DSPy**: Structured LLM prompt orchestration with schema guarantees.
- **Qdrant / pgvector**: Vector database for statutory gazette clause similarity search.

#### 3.3 Frontend Web Application
- **Next.js 14+ (App Router) / React 19 / TypeScript**: Mission-critical regulatory web portal.
- **Vanilla CSS Design System**: Custom tokenized CSS modules (zero bulky runtime libraries).
- **Zustand**: Lightweight client state management (inspection canvas, active product).
- **TanStack Query v5**: Asynchronous server state caching and SSE polling.
- **OpenSeadragon / Canvas API**: Deep zoom and interactive bounding box overlay rendering.

#### 3.4 Storage & Infrastructure
- **PostgreSQL 16**: Primary relational database with `pgvector` extension.
- **Redis 7**: High-speed memory store for task broker, session state, and FoSCoS cache.
- **MinIO / AWS S3**: S3-compatible immutable object store for high-resolution images & PDFs.
- **Docker & Docker Compose**: Containerized multi-service development and deployment.
- **Nginx / Envoy**: Reverse proxy, TLS 1.3 termination, rate-limiting, and compression.

---

### 4. Technical Risks, Challenges & Mitigation Strategies

```
+---------------------------------------------------------------------------------------------------+
|                                  RISK MATRIX & MITIGATION STRATEGY                                |
+---------------------------------------------------------------------------------------------------+
| # | Identified Risk / Challenge    | Severity | Impact on System   | Concrete Mitigation Strategy |
+---+--------------------------------+----------+--------------------+------------------------------+
| 1 | Anti-Bot Scraping Blocks on    | HIGH     | Ingestion pipeline | Implement rotating headers,  |
|   | major e-commerce platforms     |          | stalls; incomplete | residential proxy pools,     |
|   | (Cloudflare, Akamai WAF)       |          | surveillance       | JSON-LD structured data      |
|   |                                |          |                    | extraction, fallback to API. |
+---+--------------------------------+----------+--------------------+------------------------------+
| 2 | Distorted / Curved Packaging   | HIGH     | OCR failure; false | Apply 3D cylindrical TPS     |
|   | (Cans, shiny foil, wrinkles)   |          | negative non-      | unwarping, multi-scale CLAHE,|
|   |                                |          | compliance flags   | and zone-guided multi-pass   |
|   |                                |          |                    | OCR recognition.             |
+---+--------------------------------+----------+--------------------+------------------------------+
| 3 | Multi-Lingual Regional Scripts | MEDIUM   | Missing regional   | Fine-tune PaddleOCR with     |
|   | (Hindi, Tamil, Telugu labels)  |          | statutory warnings | bilingual Indian packaging   |
|   |                                |          | on rural packages  | datasets; Vision-LLM fallback|
+---+--------------------------------+----------+--------------------+------------------------------+
| 4 | LLM Hallucinations in Legal    | CRITICAL | Discredited statutory| Dual-verification design:   |
|   | Findings & Regulatory Clauses  |          | evidence in court  | deterministic rule engine for|
|   |                                |          | proceedings        | numbers; strict RAG retrieval|
|   |                                |          |                    | with mandatory gazette cites.|
+---+--------------------------------+----------+--------------------+------------------------------+
| 5 | High Compute Costs on GPU OCR  | MEDIUM   | Operational cost   | Zone-first cropping (OCR is  |
|   | & Deep Learning Inference      |          | blowouts at scale  | run only on detected text    |
|   |                                |          |                    | zones, not blank packaging); |
|   |                                |          |                    | ONNX Runtime quantization.   |
+---+--------------------------------+----------+--------------------+------------------------------+
| 6 | Chain of Custody & Evidence    | HIGH     | Defense challenges | Immutable S3 object lock,    |
|   | Admissibility Challenges       |          | in judicial court  | immediate SHA-256 hashing at |
|   |                                |          |                    | gateway edge, NTP timestamps.|
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Quality Assurance & Verification Architecture

To ensure zero false accusations and rock-solid reliability, DRISHTI establishes three rigorous testing tiers:

1. **Deterministic Regulatory Unit Suite**:
   - 500+ synthetic tests covering every threshold in the FSS (Advertising and Claims) Regulations, 2018 and (Labelling and Display) Regulations, 2020.
   - Example: Test verify that a product declaring 0.6g trans fat per 100g *must* fail a "Trans Fat Free" claim test.
2. **Vision & OCR Golden Benchmark Dataset**:
   - Curated dataset of 200 high-resolution physical packaging scans (bottles, pouches, tetra packs, cereal boxes) with human ground-truth annotations for text and bounding boxes.
   - Any model update must maintain or improve the baseline Character Error Rate (< 3.5%).
3. **End-to-End Case Flow Simulation**:
   - Automated integration tests simulating full lifecycle: Ingestion of mock e-commerce HTML -> Zone extraction -> Rule evaluation -> Dossier generation -> Officer assignment.
