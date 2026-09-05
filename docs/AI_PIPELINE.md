# DRISHTI: AI & Machine Learning Pipeline Architecture
## Phase 0: Vision, OCR, Semantic Extraction, Reasoning & Risk Intelligence

---

### 1. AI Pipeline Architectural Principles

In a legal and regulatory context, **uncontrolled probabilistic AI is dangerous**. An artificial intelligence system cannot accuse a food manufacturer of a statutory offense based on hallucinations, probabilistic drift, or vague intuition.

DRISHTI enforces a **Hybrid Neuro-Symbolic AI Paradigm**:
1. **Perception Layer (Deep Learning & Computer Vision)**: Extract raw visual elements, unwarp distorted packaging labels, segment functional zones, and transcribe multi-lingual text tokens with spatial coordinates.
2. **Structuring Layer (Information Extraction & NER)**: Transform raw OCR tokens and DOM nodes into strongly-typed Canonical Data Schemas (`CanonicalProductSpecification`).
3. **Reasoning Layer (Neuro-Symbolic Hybrid)**:
   - **Deterministic Rules Engine (Symbolic)**: Execute hard mathematical, relational, and statutory checks (numeric thresholds, banned chemical lists, date arithmetic, FSSAI checksum validation).
   - **Calibrated Semantic LLM Engine (Neural)**: Analyze ambiguous natural language marketing claims, contextual misleadingness, and implied health benefits using Retrieval-Augmented Generation (RAG) strictly grounded in statutory gazette notifications.
4. **Scoring & Explainability Layer**: Calculate mathematically transparent risk scores and generate legally grounded explanations linked directly to image pixel coordinates.

```
+---------------------------------------------------------------------------------------------------+
|                                     DRISHTI AI PIPELINE TOPOLOGY                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ STAGE 1: COMPUTER VISION & PREPROCESSING ]                                                     |
|    Image Dewarping (TPS / 3D Cylinder)  --> Glare Removal  --> Super-Resolution (Real-ESRGAN)     |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 2: LAYOUT ANALYSIS & ZONE SEGMENTATION ]                                                 |
|    YOLOv8-Doc / LayoutLMv3 Object Detection:                                                      |
|    - Nutrition Table   - Ingredients Block  - Veg/Non-Veg Symbol  - FSSAI License Stamp          |
|    - Brand & Title     - Net Quantity       - Date Marking Panel  - Manufacturer Address         |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 3: MULTI-LINGUAL OCR ENGINE ]                                                            |
|    Zone-Guided OCR (PaddleOCR v4 / TrOCR / Vision-LLM Fallback)                                   |
|    - English  - Hindi (Devanagari)  - Tamil  - Telugu  - Kannada  - Marathi                       |
|    Outputs: Text tokens + Confidence + Bounding Box Polygons                                      |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 4: CANONICAL ENTITY NORMALIZATION ]                                                      |
|    - Nutrition Parser: Regex + Key-Value Table Extractor (per 100g, per serve, units)             |
|    - Ingredient Parser: INS / E-number resolution, sub-component tree, allergen tagging           |
|    - Claim Classifier: Multi-label classification against 2018 Advertising Schedule               |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 5: DUAL-VERIFICATION REASONING ENGINE ]                                                  |
|    +-----------------------------------------+   +---------------------------------------------+  |
|    |  Deterministic Rule Engine (AST/JSON)   |   |   Grounded Semantic RAG (LLM)               |  |
|    |  - RDA Threshold checks (ICMR-NIN)      |   |   - Deceptive Marketing Semantic Analysis   |  |
|    |  - Prohibited Additives & Adulterants   |   |   - Implied Therapeutic / Medicinal Claims  |  |
|    |  - FoSCoS Checksum & Category Match     |   |   - Superlative Word Screening ("100% Pure")|  |
|    +-----------------------------------------+   +---------------------------------------------+  |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 6: CROSS-SOURCE DISCREPANCY DETECTOR ]                                                   |
|    Triangulate: [ E-Commerce Web Text ] vs. [ Physical Packaging OCR ] vs. [ FoSCoS License ]     |
|                                         │                                                         |
|                                         ▼                                                         |
|  [ STAGE 7: RISK INTELLIGENCE & EXPLAINABLE EVIDENCE (XAI) ]                                      |
|    Composite Risk Score (0-100) + Statutory Section Mapping + Visual Evidence Bounding Boxes      |
+---------------------------------------------------------------------------------------------------+
```

---

### 2. Deep Dive: Computer Vision & Layout Analysis Pipeline

Food packaging poses severe real-world vision challenges: flexible pouches crinkle, cylindrical bottles create extreme perspective distortion, shiny foil wrappers reflect scanner glare, and small text is printed at low resolutions.

#### 2.1 Packaging Normalization & Dewarping
1. **Cylinder Unwarping**: Uses 3D cylindrical surface fitting and Thin Plate Spline (TPS) transformation to rectify curved text lines on cans, jars, and bottles into planar rectangular representations.
2. **Reflection & Glare Suppression**: Multi-scale Retinex with bilateral filtering to attenuate specular glare spots caused by retail shelf lighting on plastic packaging.
3. **Contrast Normalization**: Adaptive histogram equalization (CLAHE) applied to low-contrast date stamps and dot-matrix batch codes.

#### 2.2 Zone Detection Architecture (YOLOv8-Doc / LayoutLM)
Packaging surfaces are segmented into 8 standardized statutory functional zones:
- `ZONE_NUTRITION_FACTS`: Bounding box of the nutritional disclosure table.
- `ZONE_INGREDIENTS`: Bounding box of the ingredient sequence declaration.
- `ZONE_VEG_NONVEG_LOGO`: Specific bounding box detecting the mandatory green square with filled circle or brown square with filled triangle (as mandated under Regulation 2.2.2).
- `ZONE_FSSAI_LICENSE`: 14-digit license number and accompanying FSSAI logo.
- `ZONE_DATE_MARKING`: Date of manufacture, packaging date, and "Best Before" or "Use By" date.
- `ZONE_NET_QUANTITY`: Metric net weight/volume declaration.
- `ZONE_MANUFACTURER_DETAILS`: Name, address, consumer care details of manufacturer/marketer.
- `ZONE_FRONT_MARKETING`: Prominent front-of-pack claims and brand graphics.

---

### 3. Multi-Lingual OCR Strategy

To maintain sub-second extraction without sacrificing accuracy, DRISHTI employs a **Tiered OCR Execution Model**:

```
[ Incoming Zone Crop ]
          │
          ▼
[ Resolution & Clarity Check ] ──(Low Confidence < 0.85)──▶ [ Super-Resolution Real-ESRGAN ]
          │ (Pass)
          ▼
[ Primary Engine: PaddleOCR v4 (Fine-Tuned) ]
  - Script Detection: Latin, Devanagari, Dravidian
  - Character Error Rate (CER) Target: < 3%
          │
          ├──▶ High Confidence (> 0.90) ──▶ [ Output Structured Tokens ]
          │
          └──▶ Moderate/Low Confidence (< 0.90)
                    │
                    ▼
          [ Secondary Fallback: Vision-LLM (Zero-Shot Specialized Prompting) ]
            - High-fidelity transcription of fragmented, dot-matrix or distorted text
```

---

### 4. Canonical Entity Normalization & Taxonomy Engines

Raw OCR text strings must be structured into standardized domain entities before regulatory rules can be evaluated.

#### 4.1 Ingredient Parsing & Taxonomy Resolution
- **Sub-Component Resolution**: Deconstructs nested ingredients (e.g., *"Milk Solids (Whole Milk Powder, Skimmed Milk Powder, Whey Protein Concentrate)"* -> parsed as a hierarchical composition tree).
- **INS / E-Number Mapper**: Regex and entity dictionary mapping commercial names to international numbering codes (e.g., *"Preservative 211"* -> `Sodium Benzoate [INS 211]`, *"Acidity Regulator 330"* -> `Citric Acid [INS 330]`).
- **Allergen Identifier**: Cross-references ingredients against the 8 statutory allergens declared under FSSAI 2020 Labelling Regulations:
  1. Cereals containing gluten
  2. Crustaceans and their products
  3. Eggs and egg products
  4. Fish and fish products
  5. Peanuts, tree nuts and their products
  6. Soybeans and their products
  7. Milk and milk products
  8. Sulphite in concentrations of 10mg/kg or more.

#### 4.2 Nutritional Normalization Engine
- Normalizes diverse unit formats (`kJ`, `kcal`, `mcg`, `mg`, `g`, `% RDA`, `% DV`).
- Computes dual-table structures: **Per 100g / 100ml** and **Per Specified Serving Size**.
- Cross-calculates energy balance to detect mathematical fraud:
  $$\text{Calculated Kcal} = (4 \times \text{Protein}) + (4 \times \text{Carbohydrate}) + (9 \times \text{Total Fat})$$
  If $\left| \text{Declared Kcal} - \text{Calculated Kcal} \right| > 20\%$, a mathematical non-compliance flag is triggered under Section 24 of the FSS Act.

---

### 5. Regulatory Reasoning Engine: Deterministic vs. Semantic Hybrid

```
+----------------------------------------------------------------------------------------+
|                      DUAL-VERIFICATION REGULATORY REASONING MATRIX                    |
+----------------------------------------------------------------------------------------+
|                                                                                        |
|  DETERMINISTIC RULE ENGINE (Symbolic)      |  CALIBRATED SEMANTIC RAG ENGINE (LLM)     |
|  - 100% Deterministic & Auditable         |  - Constrained Temperature (T = 0.0)      |
|  - Microsecond latency execution           |  - Mandatory Statutory Source Grounding   |
|                                            |                                           |
|  [ Evaluates ]:                            |  [ Evaluates ]:                           |
|  1. RDA Excess (> 100% RDA in Supplements) |  1. Deceptive / Exaggerated claims        |
|  2. Banned Additives (e.g. Rhodamine B)    |  2. Superlative Claims ("100% Pure")      |
|  3. FoSCoS 14-Digit Checksum               |  3. Implied Medical/Therapeutic Benefits  |
|  4. Missing Mandatory Warnings             |  4. Ambiguous Natural/Organic phrasing    |
|  5. Veg/Non-Veg Logo Dimensions            |  5. Deceptive Front-of-Pack context       |
+----------------------------------------------------------------------------------------+
```

#### 5.1 Deterministic Rule Engine Specifications
- Written in Python AST / JSON Schema Rulesets.
- Example Rule: **Claim "Trans Fat Free" Validation**
  ```python
  if declared_claim == "TRANS_FAT_FREE":
      if nutritional_table.trans_fat_g_per_100g > 0.2:
          trigger_violation(
              rule_id="FSSAI-ADV-2018-SCH-I-TF",
              clause="Schedule I, FSS (Advertising and Claims) Regulations, 2018",
              severity="HIGH",
              detail="Trans fat content exceeds 0.2g per 100g limit for trans-fat free claim."
          )
  ```

#### 5.2 Calibrated Semantic LLM Engine with Zero-Hallucination Guardrails
To prevent LLM hallucinations:
1. **Constrained Decoding & Structured Outputs**: Models are forced to output strictly valid JSON conforming to the `ComplianceFindingDTO` schema via JSON mode / grammar constraint engines.
2. **Statutory Context Injection (RAG)**: The LLM prompt is injected with the exact verbatim gazette text of the relevant FSSAI regulation retrieved via vector similarity search on `pgvector`.
3. **Evidence Span Citation**: For every flagged violation, the LLM is required to return:
   - The verbatim snippet from the packaging or listing text.
   - The exact clause from the injected regulatory text.
   - If the snippet cannot be found in the extracted OCR tokens, the finding is discarded by the post-generation validator.

---

### 6. Cross-Source Consistency & Discrepancy Engine

The cross-source engine executes pairwise and 3-way alignment across three distinct representations of the same SKU:

```
                  [ Web E-Commerce Listing ]
                              ▲
                             / \
                            /   \
                           /     \
                          ▼       ▼
 [ Packaging Label OCR ] ◀─────────▶ [ FoSCoS Registry Record ]
```

#### Discrepancy Classification Taxonomy:
1. **Direct Contradiction**: Web page advertises "Zero Sugar / Keto", but packaging label discloses 22g of added sugar.
2. **Deceptive Omission**: Packaging label discloses "Contains Artificial Sweetener (Acesulfame K)", but the e-commerce listing omits this warning.
3. **Licensing Entity Mismatch**: E-commerce seller claims the product is manufactured by "Alpha Foods Mumbai", but the 14-digit FSSAI number resolves on FoSCoS to a closed facility in "Beta Enterprises Kanpur".
4. **Scope Exceedance**: FoSCoS registration covers "Dairy Products", but the product being sold under that license is an alcoholic beverage or health supplement.

---

### 7. Risk Intelligence & Scoring Formulation

DRISHTI computes a transparent, composite **Product Compliance Risk Score ($R_{prod}$)** on a normalized scale from **0.0 to 100.0**:

$$R_{prod} = \min\left(100.0, \; w_h \cdot H + w_d \cdot D + w_l \cdot L + w_m \cdot M\right) \times V_{multiplier}$$

Where:
- **$H$ (Health Hazard Severity, 0-100)**: Reflects toxicological risk, undeclared allergens, banned food additives, or toxic contaminants.
  - *Weights*: Banned color/adulterant = 95; Undeclared major allergen = 85; Excessive vitamin dosage = 60.
- **$D$ (Deception & Misleading Severity, 0-100)**: Reflects economic fraud, false health cures, and cross-source contradictions.
  - *Weights*: False medical cure = 80; Direct web-to-pack contradiction = 70; Missing veg/non-veg symbol = 40.
- **$L$ (Licensing & Regulatory Integrity, 0-100)**: Reflects licensing fraud.
  - *Weights*: Non-existent/fake FSSAI number = 100; Expired license = 85; Category scope mismatch = 65.
- **$M$ (Labeling & Packaging Technical Defects, 0-100)**: Reflects mandatory layout non-compliances.
  - *Weights*: Missing Date/Expiry = 75; Missing Net Wt = 30; Minor font-size defect = 15.
- **$w_h, w_d, w_l, w_m$ (Domain Weights)**: Normalized weights ($w_h = 0.40$, $w_d = 0.25$, $w_l = 0.25$, $w_m = 0.10$).
- **$V_{multiplier}$ (Vulnerability Multiplier)**:
  - Infant food / Baby formula: $1.25$
  - Dietary supplements for chronic disease: $1.15$
  - General food commodities: $1.00$

#### Risk Tier Classification:
- **CRITICAL RISK ($80.0 \le R \le 100.0$)**: Immediate health hazard or fraudulent licensing. Triggers automatic Priority-1 alert to Designated Officer for on-site seizure.
- **HIGH RISK ($60.0 \le R < 80.0$)**: Substantial deception or major allergen omission. Triggers Section 32 Improvement Notice recommendation.
- **MEDIUM RISK ($40.0 \le R < 60.0$)**: Ambiguous claims or secondary labeling defects. Scheduled for routine field verification.
- **LOW / COMPLIANT ($0.0 \le R < 40.0$)**: Minor or no infractions. Archived into continuous monitoring surveillance pool.

---

### 8. Explainable AI (XAI) & Evidence Dossier Output

To ensure findings stand up in court or before an Adjudicating Officer, every finding generates an **XAI Justification Block**:

```
+----------------------------------------------------------------------------------------+
|                               XAI JUSTIFICATION RECORD                                 |
+----------------------------------------------------------------------------------------+
| Finding ID: VIOL-2026-KA-094                                                           |
| Finding Title: Illegal Disease Risk Reduction Claim                                   |
| Risk Contribution: +28.5 points                                                        |
|----------------------------------------------------------------------------------------|
| Visual Bounding Box: [x1: 140, y1: 220, x2: 680, y2: 340] on Front-of-Pack Image     |
| Raw Extracted Text: "Clinically proven to reverse Type-2 Diabetes in 30 days"        |
| Normalized Claim Type: THERAPEUTIC_CURE_CLAIM                                          |
|----------------------------------------------------------------------------------------|
| Statutory Violation:                                                                   |
|   - Food Safety and Standards Act, 2006: Section 24 (Misleading Advertisements)        |
|   - FSS (Advertising and Claims) Regulations, 2018: Regulation 4(7)                   |
|   - Statutory Text: "No food business operator shall make any claim regarding cure,   |
|     mitigation or treatment of any specific disease or disorder."                      |
|----------------------------------------------------------------------------------------|
| Algorithmic Determination Logic:                                                       |
|   1. Entity "Type-2 Diabetes" resolved to ICD-11 Code 5A11 (Chronic Disease).          |
|   2. Semantic verb "reverse" classified as absolute curative claim.                    |
|   3. FSSAI gazette strictly prohibits curative claims without Central Approval.        |
|   4. Zero records of Central Advisory Committee exemption found in FoSCoS registry.   |
+----------------------------------------------------------------------------------------+
```
