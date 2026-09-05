import { getStoredToken } from '@/lib/auth';
import { SystemHealth } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function fetchSystemHealth(): Promise<SystemHealth> {
  try {
    const res = await fetch(`${API_BASE_URL}/health?check_db=true`, {
      cache: 'no-store',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}`);
    }

    return await res.json();
  } catch (error) {
    return {
      status: 'offline',
      project: 'DRISHTI Compliance Risk Intelligence Platform',
      version: '0.1.0',
      environment: 'development',
      timestamp: new Date().toISOString(),
      database: {
        status: 'disconnected',
        error: error instanceof Error ? error.message : 'Backend unreachable',
      },
    };
  }
}

export interface DashboardMetricsData {
  total_cases: number;
  cases_under_analysis: number;
  low_risk: number;
  medium_risk: number;
  high_risk: number;
  pending_review: number;
}

export interface CaseListItem {
  case_id: string;
  case_number: string;
  product_name: string;
  brand: string;
  category: string;
  submission_date: string;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  status: string;
  priority: string;
  title: string;
}

export async function fetchDashboardMetrics(): Promise<DashboardMetricsData> {
  const token = getStoredToken();
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/cases/metrics`, {
      headers: {
        'Accept': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return await res.json();
  } catch {
    // Fallback seed baseline for development if server is unreachable
    return {
      total_cases: 6,
      cases_under_analysis: 2,
      low_risk: 1,
      medium_risk: 2,
      high_risk: 3,
      pending_review: 3,
    };
  }
}

export async function fetchRecentCases(limit: number = 10, riskLevel?: string): Promise<CaseListItem[]> {
  const token = getStoredToken();
  const url = new URL(`${API_BASE_URL}/api/v1/cases/recent`);
  url.searchParams.set('limit', limit.toString());
  if (riskLevel && riskLevel !== 'ALL') {
    url.searchParams.set('risk_level', riskLevel);
  }

  try {
    const res = await fetch(url.toString(), {
      headers: {
        'Accept': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return await res.json();
  } catch {
    // Fallback demonstration cases for development
    return [
      {
        case_id: 'c1',
        case_number: 'FSSAI-CASE-2026-0042',
        product_name: 'AyurVital Diabetic Care Shake',
        brand: 'AyurVital Health',
        category: 'HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS',
        submission_date: new Date(Date.now() - 86400000).toISOString(),
        risk_level: 'CRITICAL',
        risk_score: 88.5,
        status: 'FIELD_INSPECTION_ORDERED',
        priority: 'URGENT_P1',
        title: 'Illegal Curative Diabetes Claim on AyurVital Shake',
      },
      {
        case_id: 'c2',
        case_number: 'FSSAI-CASE-2026-0043',
        product_name: 'PureKeto Energy Bar Deluxe',
        brand: 'NutriPure Brands',
        category: 'CEREAL_AND_CONFECTIONERY',
        submission_date: new Date(Date.now() - 172800000).toISOString(),
        risk_level: 'HIGH',
        risk_score: 76.0,
        status: 'NOTICE_ISSUED_SEC32',
        priority: 'HIGH_P2',
        title: 'Undeclared High Added Sugars (18g vs 0g Web Claim)',
      },
      {
        case_id: 'c3',
        case_number: 'FSSAI-CASE-2026-0044',
        product_name: 'Himalayan Shilajit Pure Resin',
        brand: 'MountainHerbs',
        category: 'AYURVEDIC_PROPRIETARY',
        submission_date: new Date(Date.now() - 259200000).toISOString(),
        risk_level: 'MEDIUM',
        risk_score: 52.0,
        status: 'TRIAGED',
        priority: 'ROUTINE_P3',
        title: 'Unsubstantiated Stamina & Anti-Aging Claims',
      },
      {
        case_id: 'c4',
        case_number: 'FSSAI-CASE-2026-0045',
        product_name: 'Organic Cold-Pressed Mustard Oil',
        brand: 'BharatAgro',
        category: 'EDIBLE_OILS_AND_FATS',
        submission_date: new Date(Date.now() - 345600000).toISOString(),
        risk_level: 'LOW',
        risk_score: 18.0,
        status: 'RESOLVED',
        priority: 'MONITORING_P4',
        title: 'Routine Market Surveillance Sample - Compliant',
      },
      {
        case_id: 'c5',
        case_number: 'FSSAI-CASE-2026-0046',
        product_name: 'NutriGrow Fortified Infant Formula',
        brand: 'EarlyCare',
        category: 'INFANT_FOODS_AND_FORMULA',
        submission_date: new Date(Date.now() - 432000000).toISOString(),
        risk_level: 'CRITICAL',
        risk_score: 84.0,
        status: 'SAMPLE_DRAWN',
        priority: 'URGENT_P1',
        title: 'Excess Vitamin A Exceeding Tolerable Upper Limit (RDA 2022)',
      },
      {
        case_id: 'c6',
        case_number: 'FSSAI-CASE-2026-0047',
        product_name: 'Herbal Glow Ayurvedic Detox Tea',
        brand: 'GreenLeaf',
        category: 'BEVERAGES_TEA_AND_COFFEE',
        submission_date: new Date(Date.now() - 518400000).toISOString(),
        risk_level: 'MEDIUM',
        risk_score: 45.0,
        status: 'ASSIGNED',
        priority: 'ROUTINE_P3',
        title: 'Missing Mandatory Warning on Senna Leaves Content',
      },
    ];
  }
}

export async function submitProduct(formData: FormData) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || data?.message || 'Submission failed');
  }
  return data;
}

export async function fetchCaseDetail(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}`, {
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || data?.message || 'Failed to load case detail');
  }
  return data;
}

export async function runDeepAnalysis(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/deep-analysis`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Deep analysis failed');
  return data;
}

export async function runRiskAssessment(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/risk-assessment`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Risk assessment failed');
  return data;
}

export async function runConsistencyCheck(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/consistency-check`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Consistency check failed');
  return data;
}

export async function fetchCaseExplanation(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/explanation`, {
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to load explanation');
  return data;
}

// ─── Phase B2: Unified End-to-End Analysis Pipeline ─────────────────────────
// Calls POST /api/v1/cases/{caseId}/run-analysis
// Orchestrates: OCR → Structuring → Deep Analysis → Consistency → Risk
// Returns CasePipelineResult with risk_score, risk_level, confidence_score.

export interface PipelineResult {
  case_id: string;
  case_number: string;
  product_id: string;
  status: string;
  previous_status: string;
  priority: string;
  ocr_processed: boolean;
  images_processed: number;
  intelligence_completed: boolean;
  deep_analysis_completed: boolean;
  consistency_completed: boolean;
  risk_assessment_completed: boolean;
  risk_score: number | null;
  risk_level: string | null;
  confidence_score: number | null;
  total_findings: number;
  errors: string[];
  execution_timestamp: string;
  execution_duration_ms: number;
}

export async function runPipelineAnalysis(caseId: string): Promise<PipelineResult> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/run-analysis`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.message || data?.detail || 'Pipeline analysis failed');
  }
  return data;
}

// ─── Phase 13: Evidence Management System ───────────────────────────────────

export interface EvidenceRecord {
  record_id: string;
  evidence_type: 'URL' | 'IMAGE' | 'OCR_TEXT' | 'SUBMITTED_TEXT' | 'EXTRACTED_DATA' | 'AI_ANALYSIS_NOTE';
  evidence_origin: 'PRIMARY_SOURCE' | 'OCR_EXTRACTED' | 'SUBMITTED_TEXT' | 'AI_ANALYSIS' | 'SYSTEM_GENERATED';
  ai_generated: boolean;
  content_text?: string | null;
  content_uri?: string | null;
  source_type: string;
  source_reference?: string | null;
  sha256_hash?: string | null;
  capture_timestamp?: string | null;
  confidence?: number | null;
  metadata?: Record<string, any>;
}

export interface FindingEvidenceBundle {
  finding_id: string;
  finding_title: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  source: string;
  why_flagged: string;
  rule_code?: string | null;
  statutory_reference?: string | null;
  source_metadata?: Record<string, any>;
  primary_evidence: EvidenceRecord[];
  ai_analysis_notes: EvidenceRecord[];
}

export interface CaseEvidencePackage {
  case_id: string;
  case_number: string;
  product_id: string;
  product_name?: string | null;
  brand?: string | null;
  category?: string | null;
  submission_timestamp?: string | null;
  url_evidence: EvidenceRecord[];
  image_evidence: EvidenceRecord[];
  ocr_evidence: EvidenceRecord[];
  submitted_text_evidence: EvidenceRecord[];
  extracted_data_evidence: EvidenceRecord[];
  finding_bundles: FindingEvidenceBundle[];
  total_evidence_records: number;
  total_findings_with_evidence: number;
  coverage_percentage: number;
  generated_at: string;
  integrity_note: string;
}

export interface EvidenceIntegrityCheckResult {
  case_id: string;
  case_number: string;
  all_findings_linked: boolean;
  total_findings: number;
  findings_with_evidence: number;
  ai_separation_verified: boolean;
  unmarked_ai_items_found: number;
  hash_verification_passed: boolean;
  total_hashed_items: number;
  valid_hashes: number;
  timestamps_valid: boolean;
  integrity_score: number;
  verification_details: string[];
  verified_at: string;
}

export async function fetchCaseEvidencePackage(caseId: string): Promise<CaseEvidencePackage> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/evidence-package`, {
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to load evidence package');
  return data;
}

export async function verifyEvidenceIntegrity(caseId: string): Promise<EvidenceIntegrityCheckResult> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/evidence-package/verify`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Evidence verification failed');
  return data;
}

// ---------------------------------------------------------------------------
// Phase 14: Priority Review Queue & Authority Case Management
// ---------------------------------------------------------------------------

export interface PriorityQueueItem {
  case_id: string;
  case_number: string;
  product_id: string;
  product_name: string;
  brand?: string | null;
  category?: string | null;
  status: string;
  priority: string;
  risk_score?: number | null;
  risk_level?: string | null;
  confidence_score?: number | null;
  has_critical_findings: boolean;
  has_high_findings: boolean;
  created_at: string;
  submitted_at?: string | null;
  assigned_officer_id?: string | null;
  total_findings: number;
}

export interface PriorityQueueResponse {
  items: PriorityQueueItem[];
  total: number;
  limit: number;
  offset: number;
  urgent_count: number;
  high_count: number;
  standard_count: number;
}

export interface CaseReviewSubmission {
  action: string;
  notes: string;
  assigned_to?: string | null;
  statutory_deadline_days?: number | null;
  target_status?: string | null;
}

export interface CaseStatusUpdate {
  status: string;
  reason?: string | null;
}

export interface PriorityQueueQueryParams {
  search?: string;
  status?: string;
  risk_level?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export async function fetchPriorityQueue(params: PriorityQueueQueryParams = {}): Promise<PriorityQueueResponse> {
  const token = getStoredToken();
  const query = new URLSearchParams();
  if (params.search) query.append('search', params.search);
  if (params.status) query.append('status', params.status);
  if (params.risk_level) query.append('risk_level', params.risk_level);
  if (params.sort_by) query.append('sort_by', params.sort_by);
  if (params.sort_order) query.append('sort_order', params.sort_order);
  if (params.limit !== undefined) query.append('limit', String(params.limit));
  if (params.offset !== undefined) query.append('offset', String(params.offset));

  const url = `${API_BASE_URL}/api/v1/cases/priority-queue${query.toString() ? `?${query.toString()}` : ''}`;
  const res = await fetch(url, {
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to fetch priority queue');
  return data;
}

export async function startCaseReview(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/start-review`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to initiate case review');
  return data;
}

export async function submitCaseReview(caseId: string, review: CaseReviewSubmission) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/reviews`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(review),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to record authority review');
  return data;
}

export async function updateCaseStatus(caseId: string, statusUpdate: CaseStatusUpdate) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(statusUpdate),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to update case status');
  return data;
}

// ---------------------------------------------------------------------------
// Phase 15: Evidence-Backed Compliance Report Generation
// ---------------------------------------------------------------------------

export interface CaseComplianceReportData {
  report_title: string;
  report_identifier: string;
  generated_at: string;
  generating_system: string;
  case_info: {
    case_id: string;
    case_number: string;
    created_at: string;
    status: string;
    priority: string;
    assigned_officer?: string | null;
    jurisdiction?: string | null;
  };
  product_info: {
    product_name: string;
    brand?: string | null;
    category?: string | null;
    manufacturer?: string | null;
    fssai_license_number?: string | null;
  };
  source_info: {
    product_url?: string | null;
    platform?: string | null;
    submitted_description?: string | null;
    submitted_images: Array<{
      image_id?: string | null;
      image_type: string;
      image_url?: string | null;
      sha256_hash?: string | null;
      file_name?: string | null;
    }>;
    submission_notes?: string | null;
  };
  risk_assessment: {
    risk_score: number;
    risk_level: string;
    confidence_score: number;
    total_findings_analyzed: number;
    data_completeness_ratio: number;
    score_explanation?: string | null;
    dimension_breakdown: Array<{
      dimension: string;
      finding_count: number;
      max_severity: string;
      weighted_contribution: number;
      raw_dimension_score: number;
      confidence: number;
    }>;
    assessment_timestamp?: string | null;
  };
  detected_findings: Array<{
    finding_id: string;
    title: string;
    description: string;
    severity: string;
    confidence: number;
    dimension: string;
    rule_code?: string | null;
    statutory_reference?: string | null;
    why_flagged?: string | null;
  }>;
  evidence: Array<{
    evidence_id: string;
    evidence_type: string;
    source: string;
    extracted_text?: string | null;
    image_url?: string | null;
    sha256_hash?: string | null;
    confidence_score?: number | null;
    timestamp: string;
    linked_finding_ids: string[];
  }>;
  analysis_limitations: {
    missing_information: string[];
    ocr_limitations: string[];
    ai_confidence_limitations: string[];
    data_completeness_ratio: number;
    overall_completeness_assessment: string;
  };
  review_recommendation: {
    recommendation: string;
    priority_level: string;
    recommendation_reason: string;
    suggested_actions: string[];
    statutory_notice_recommended: boolean;
    sampling_recommended: boolean;
    lab_referral_recommended: boolean;
  };
  mandatory_statutory_disclaimer: string;
  legal_framework_notice: string;
  sha256_report_hash?: string | null;
}

export async function fetchCaseReportData(caseId: string): Promise<CaseComplianceReportData> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/report/data`, {
    headers: {
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    cache: 'no-store',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || 'Failed to fetch compliance report data');
  return data;
}

export async function downloadCaseReportPdf(caseId: string, caseNumber?: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/report/pdf`, {
    headers: {
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData?.detail || 'Failed to download PDF report');
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `DRISHTI-Report-${caseNumber || caseId}.pdf`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function openCaseReportHtml(caseId: string) {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${caseId}/report/html`, {
    headers: {
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData?.detail || 'Failed to open HTML report');
  }
  const html = await res.text();
  const win = window.open('', '_blank');
  if (win) {
    win.document.write(html);
    win.document.close();
  }
}




