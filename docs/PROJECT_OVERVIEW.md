# DRISHTI: AI-Powered Product Compliance Risk Intelligence System
## Phase 0: Project Overview & Strategic Foundation

---

### 1. Executive Summary

**DRISHTI** (*Digital Regulatory Intelligence & Surveillance for Holistic Threat Identification*) is an enterprise-grade, AI-powered compliance risk intelligence platform engineered specifically for food regulatory authorities (such as the **Food Safety and Standards Authority of India - FSSAI**, state food safety administrations, and designated enforcement officers).

With the exponential surge in e-commerce grocery platforms (quick-commerce, dark stores, online marketplaces, and Direct-to-Consumer [D2C] brands), regulatory authorities face an unprecedented challenge: millions of active Food Business Operator (FBO) Stock Keeping Units (SKUs) are marketed with unsubstantiated claims, non-compliant labeling, unapproved ingredients, adulterants, or fraudulent licensing credentials. Manual inspections cover less than 1% of products in circulation.

DRISHTI closes this enforcement gap by providing an end-to-end automated surveillance, multi-modal ingestion, cross-source discrepancy detection, risk triage, and regulatory evidence generation pipeline. By unifying computer vision (OCR, packaging geometry, visual element verification), natural language understanding (claim deconstruction, ingredient taxonomy parsing), deterministic regulatory rules, and explainable AI (XAI), DRISHTI empowers Food Safety Officers (FSOs) and Designated Officers (DOs) to transition from reactive inspections to predictive, risk-prioritized enforcement.

---

### 2. Statutory and Regulatory Context

DRISHTI is structurally aligned with the statutory mandates and subordinate regulations under the **Food Safety and Standards Act, 2006 (Act No. 34 of 2006)**:

| Statutory Regulation / Act Section | Regulatory Domain & Enforcement Scope | DRISHTI Automated Verification Focus |
|---|---|---|
| **FSS Act 2006, Section 23 & 24** | Packaging and labelling of food; Prohibition of misleading advertisements & unfair trade practices | Detection of unapproved health/medicinal claims, deceptive branding, and non-disclosure of critical warnings. |
| **FSS (Labelling and Display) Regulations, 2020** | Mandatory labeling elements, font dimensions, area ratios, bilingual requirements, and symbol placement | Validation of Veg/Non-Veg logos, FSSAI logo & license positioning, Nutritional Facts per 100g/serving, allergen declarations, Date of Manufacture, Expiry/Best Before, and Net Quantity. |
| **FSS (Advertising and Claims) Regulations, 2018 (with 2021 Amendments)** | Substantiation of nutrient content claims, comparative claims, health claims, and risk reduction claims | Verification of threshold criteria (e.g., qualifying conditions for "High Protein", "Trans-Fat Free", "Sugar-Free"), screening for forbidden superlative words ("Natural", "Pure", "Fresh", "Authentic", "Miracle"). |
| **FSS (Food Products Standards and Food Additives) Regulations, 2011** | Permitted food additives, synthetic colors, artificial sweeteners, maximum residue limits (MRLs), and heavy metals | Extraction of INS/E-numbers, identification of unapproved additives, screening for prohibited adulterants (e.g., Rhodamine B, Metanil Yellow, Melamine). |
| **FSS (Health Supplements, Nutraceuticals, Food for Special Dietary Use...) Regulations, 2022** | Pre-market approval, RDA limits for vitamins/minerals, prohibited botanicals, and mandatory cautionary statements | Validation of vitamin/mineral dosages against ICMR-NIN RDA limits; identification of scheduled botanicals and missing advisory labels ("Not for medicinal use", "Keep out of reach of children"). |
| **FSS (Licensing and Registration of Food Businesses) Regulations, 2011** | Mandatory 14-digit licensing, category endorsement, FoSCoS synchronization | Algorithmic checksum validation of 14-digit FSSAI license numbers, category-license matching via FoSCoS registry, premises-marketer discrepancy checks. |

---

### 3. Core Project Mission and Objectives

1. **Autonomous Multi-Channel Surveillance**: Continually monitor e-commerce listings, marketplace catalog pages, and social-commerce channels for newly listed or modified food products.
2. **Multi-Modal Data Ingestion**: Accept heterogeneous authority submissions, including direct e-commerce product URLs, front-of-pack (FOP) and back-of-pack (BOP) smartphone captures, warehouse bulk scans, and raw text descriptions.
3. **High-Fidelity Document & Packaging Vision**: Decouple and normalize curved, crumpled, reflective, or low-resolution packaging labels using deep learning-based visual unwarping, multi-zone layout detection, and multi-lingual OCR (English, Hindi, and regional Indian languages).
4. **Cross-Source Consistency Verification**: Automatically identify discrepancies between what is advertised on digital storefronts (e.g., "100% Organic, Zero Sugar") versus what is printed on physical packaging labels (e.g., "Contains 18g Added Sugars, Sucralose") versus what is registered in the official FoSCoS database.
5. **Deterministic & Semantic Risk Scoring**: Compute a transparent, weighted compliance risk score (0 to 100) combining strict regulatory infractions (banned chemicals, invalid licenses) with probabilistic semantic violations (misleading claims).
6. **Legally Admissible Evidence Generation**: Generate cryptographically hashed, timestamped Evidence Dossiers citing exact legislative clauses, side-by-side visual crops, and audit logs suitable for issuing Improvement Notices (Section 32), Seizure Orders (Section 38), or launching adjudication proceedings.
7. **Empowering the Authority Workflow**: Provide a modern, role-based inspection management portal enabling FSOs to triage high-risk products, schedule field samplings, log lab reports, and manage enforcement actions.

---

### 4. System Scope Definition

```
+---------------------------------------------------------------------------------------+
|                                    IN SCOPE                                           |
+---------------------------------------------------------------------------------------+
| * Multi-modal ingestion: URLs (scraped), label images (FOP/BOP), raw text descriptions  |
| * Vision pipeline: image preprocessing, label unwarping, layout analysis, OCR        |
| * Canonical entity normalization: nutritional panels, ingredient lists, additives    |
| * Regulatory compliance analysis against FSSAI acts, rules, and statutory schedules   |
| * FoSCoS license validation: format checksum, status lookup, category scope match   |
| * Cross-source consistency engine (E-commerce vs. Packaging vs. Regulatory Registry)  |
| * Hybrid risk scoring model (Deterministic rule engine + calibrated AI severity)      |
| * Explainable AI (XAI) output: cited regulations, reason trees, visual bounding boxes |
| * Cryptographic evidence dossier generation (PDF/A, JSON-LD, SHA-256 tamper seal)    |
| * Role-based authority inspection triage, workflow management, and feedback tracking  |
+---------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------+
|                                  OUT OF SCOPE                                         |
+---------------------------------------------------------------------------------------+
| * Automated direct legal prosecution or penalty debiting without human officer signoff|
| * Physical wet-lab testing instrument hardware integration (Spectrometry/Chromatography)
| * End-consumer commercial shopping app or public consumer product rating portal      |
| * Direct enforcement actions on third-party marketplace servers (auto-takedowns)      |
| * Non-food commodity tracking (e.g., cosmetics, pharmaceuticals, medical devices)     |
+---------------------------------------------------------------------------------------+
```

---

### 5. Stakeholder Personas & Operational User Journeys

#### Persona 1: Food Safety Officer (FSO) / Field Inspector
- **Role**: Field-level enforcement, on-site sampling, preliminary verification of retail outlets and dark stores.
- **Operational Need**: Rapid smartphone upload of product packaging while inspecting a supermarket or dark store shelf; instant risk classification and automated identification of missing mandatory labels or mismatched license numbers.
- **Key Flow**: Upload 3 images (Front, Back, FSSAI license section) -> Receive instant high-risk alert highlighting missing Veg/Non-Veg logo and undeclared Tartrazine -> Initiate Form VA sampling notice.

#### Persona 2: Designated Officer (DO) / District Licensing Authority
- **Role**: District jurisdiction head, review of FSO inspection requests, issuing Section 32 Improvement Notices or suspension of licenses.
- **Operational Need**: Macro-level dashboard of high-risk violations across their district; access to structured, legally defensible evidence dossiers before issuing formal statutory notices.
- **Key Flow**: Review prioritized triage queue -> Open Case Dossier with side-by-side image-to-claim evidence -> Sign off on Inspection Order -> Assign to territorial FSO.

#### Persona 3: Central Surveillance & Intelligence Analyst (HQ / FSSAI Central)
- **Role**: Macro trend analysis, monitoring national e-commerce aggregators, identifying systemic non-compliance patterns across national brands.
- **Operational Need**: Batch URL ingestion of catalog dumps; queryable knowledge graph of cross-brand manufacturer infractions; analysis of recurring fraudulent claims (e.g., unapproved "diabetic friendly" rice claims).
- **Key Flow**: Submit bulk CSV of 10,000 product URLs from major quick-commerce platforms -> Monitor automated batch pipeline -> Filter products with Risk Score > 80 -> Issue national advisory to state enforcement bodies.

#### Persona 4: Legal & Adjudication Officer
- **Role**: Presenting compliance infraction cases before the Adjudicating Officer / Food Safety Appellate Tribunal.
- **Operational Need**: Tamper-proof, immutable digital audit trails showing exact date/time of online scrape or physical label capture, with verified hash integrity and direct statutory cross-references.
- **Key Flow**: Export certified Evidence Dossier (PDF/A-1b with SHA-256 signature) directly into tribunal evidentiary submission binder.

---

### 6. High-Level System Capabilities Matrix

| System Capability | Target Performance Metric | Core Output Artifact |
|---|---|---|
| **E-Commerce Web Extraction** | < 8s per listing; > 95% accuracy for price, title, ingredients, nutritional claims | Normalized Product Listing JSON |
| **Packaging Image Preprocessing** | < 2s per image; support up to 4K resolution; unwarp up to 30° cylinder curvature | Dewarped, normalized, contrast-enhanced image |
| **Label Layout Analysis** | Precision > 94%, Recall > 92% across 8 standardized label zones | Bounding box coordinates with zone taxonomy labels |
| **Multi-Lingual OCR** | Character Error Rate (CER) < 3.5% on English; CER < 6% on Hindi / Indian scripts | Normalized text stream with bounding box anchors |
| **Nutritional & Ingredient Entity Parsing** | F1-Score > 0.95 on standard nutrient tables; > 92% on complex INS additive extraction | Structured `CanonicalProductSpecification` model |
| **Regulatory Claim Verification** | 100% deterministic accuracy on numeric thresholds; > 90% semantic agreement on qualitative claims | Clause-level violation breakdown with citations |
| **FoSCoS License Verification** | < 1.5s lookup; 100% algorithmic verification of 14-digit schema | FoSCoS registry verification status model |
| **Cross-Source Discrepancy Engine** | Identifies 100% of explicit contradictions between Web vs. Label | Structured Discrepancy Matrix (Web vs. Label vs. FoSCoS) |
| **Risk Scoring Engine** | Execution < 50ms; dynamic scale 0 to 100 with category weighting | Composite Risk Score, Tier (Critical/High/Med/Low), Severity vector |
| **Evidence Dossier Generation** | < 4s per comprehensive multi-page PDF/A document | Certified Evidence Dossier PDF/A + JSON-LD package |

---

### 7. Governance, Integrity, and Ethical AI Principles

1. **Zero Hallucination Tolerance in Regulatory Claims**: LLMs and probabilistic models are strictly forbidden from asserting compliance violations without deterministic ground-truth verification against statutory text. The system employs a **Dual-Verification Architecture** where probabilistic extraction is validated by deterministic rule engines.
2. **Chain of Custody & Auditability**: Every data point, from raw image pixels to bounding box crops to extracted token strings, retains an unbroken lineage pointer. If an FSO questions why a claim was flagged, the system displays the exact image coordinate, the raw extracted text, the normalized entity, and the exact clause of the 2018 Advertising Regulations.
3. **Human-in-the-Loop Supremacy**: DRISHTI is an intelligence amplifier, not an autonomous legal prosecutor. The system cannot initiate punitive legal sanctions autonomously; it serves as a decision-support instrument generating prioritized evidence for human statutory officers.
