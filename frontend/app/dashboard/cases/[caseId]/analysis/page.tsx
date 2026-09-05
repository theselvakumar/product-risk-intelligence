'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  fetchCaseExplanation,
  runPipelineAnalysis,
  type PipelineResult,
  downloadCaseReportPdf,
  openCaseReportHtml,
} from '@/services/api';

// ─── Types ───────────────────────────────────────────────────────────────────

interface EvidenceItem {
  evidence_type: string;
  raw_text: string;
  source_type: string;
  source_reference?: string;
}

interface FindingExplanation {
  finding_id: string;
  finding_title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  source: string;
  confidence: number;
  rule_code?: string;
  statutory_reference?: string;
  reason_for_flagging: string;
  evidence: EvidenceItem[];
  discrepancy_details?: Record<string, unknown>;
}

interface RiskScoreExplanation {
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  confidence_score: number;
  score_explanation: string;
  contributing_factors: Array<{
    dimension: string;
    finding_count: number;
    max_severity: string;
    weighted_contribution: number;
    raw_dimension_score: number;
    confidence: number;
  }>;
  data_completeness_ratio: number;
  disclaimer: string;
}

interface ProductSummary {
  product_id: string;
  product_name?: string;
  brand?: string;
  category?: string;
  manufacturer?: string;
  fssai_license_number?: string;
}

interface ExplanationReport {
  case_id: string;
  case_number: string;
  product: ProductSummary;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  findings: FindingExplanation[];
  risk_assessment?: RiskScoreExplanation;
  why_flagged_summary: string[];
  generated_at: string;
  provenance_note: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  CRITICAL: { color: 'text-red-700 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/40', border: 'border-red-200 dark:border-red-800', dot: 'bg-red-500', label: 'Critical' },
  HIGH:     { color: 'text-orange-700 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-950/40', border: 'border-orange-200 dark:border-orange-800', dot: 'bg-orange-500', label: 'High' },
  MEDIUM:   { color: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40', border: 'border-amber-200 dark:border-amber-800', dot: 'bg-amber-500', label: 'Medium' },
  LOW:      { color: 'text-blue-700 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/40', border: 'border-blue-200 dark:border-blue-800', dot: 'bg-blue-400', label: 'Low' },
  INFO:     { color: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-50 dark:bg-slate-900/40', border: 'border-slate-200 dark:border-slate-700', dot: 'bg-slate-400', label: 'Info' },
};

const RISK_LEVEL_CONFIG = {
  HIGH:   { color: 'text-red-700 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/60', border: 'border-red-300 dark:border-red-700', gaugeColor: '#ef4444' },
  MEDIUM: { color: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/60', border: 'border-amber-300 dark:border-amber-700', gaugeColor: '#f59e0b' },
  LOW:    { color: 'text-emerald-700 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/60', border: 'border-emerald-300 dark:border-emerald-700', gaugeColor: '#10b981' },
};

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.INFO;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${cfg.color} ${cfg.bg} border ${cfg.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-500 dark:text-slate-400 w-9 text-right">{pct}%</span>
    </div>
  );
}

function RiskGauge({ score, level }: { score: number; level: string }) {
  const cfg = RISK_LEVEL_CONFIG[level as keyof typeof RISK_LEVEL_CONFIG] || RISK_LEVEL_CONFIG.LOW;
  const pct = Math.round(score * 100);
  const r = 52;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.75;
  const offset = arc - (arc * pct) / 100;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-40 h-32">
        <svg viewBox="0 0 120 96" className="w-full h-full" style={{ transform: 'rotate(135deg)' }}>
          <circle cx="60" cy="60" r={r} fill="none" stroke="currentColor" strokeWidth="10"
            className="text-slate-200 dark:text-slate-700"
            strokeDasharray={`${arc} ${circ}`} strokeLinecap="round" />
          <circle cx="60" cy="60" r={r} fill="none" stroke={cfg.gaugeColor} strokeWidth="10"
            strokeDasharray={`${arc - offset} ${circ}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.4, 0, 0.2, 1)' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ paddingTop: '12px' }}>
          <span className={`text-3xl font-black tabular-nums ${cfg.color}`}>{pct}</span>
          <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Score</span>
        </div>
      </div>
      <span className={`px-3 py-1 rounded-full text-sm font-black uppercase tracking-widest ${cfg.color} ${cfg.bg} border ${cfg.border}`}>
        {level} RISK
      </span>
    </div>
  );
}

// ─── Finding Card ─────────────────────────────────────────────────────────────

function FindingCard({ finding, index }: { finding: FindingExplanation; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.INFO;

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} overflow-hidden transition-all duration-200`}>
      <button
        id={`finding-${finding.finding_id}`}
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-4 flex items-start gap-4"
      >
        <div className="flex-shrink-0 mt-0.5">
          <span className="text-slate-400 dark:text-slate-500 font-mono text-xs">#{String(index + 1).padStart(2, '0')}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <span className={`text-sm font-bold ${cfg.color}`}>{finding.finding_title}</span>
            <SeverityBadge severity={finding.severity} />
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">{finding.reason_for_flagging}</p>
        </div>
        <svg className={`w-4 h-4 flex-shrink-0 text-slate-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-5 border-t border-current/10 space-y-4 pt-4">
          {/* Description */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-1">Description</div>
            <p className="text-sm text-slate-700 dark:text-slate-300">{finding.description}</p>
          </div>

          {/* Metadata row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Source</div>
              <div className="text-xs font-mono text-slate-600 dark:text-slate-400">{finding.source}</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Confidence</div>
              <ConfidenceBar value={finding.confidence} />
            </div>
            {finding.rule_code && (
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Rule Code</div>
                <div className="text-xs font-mono text-slate-600 dark:text-slate-400">{finding.rule_code}</div>
              </div>
            )}
            {finding.statutory_reference && (
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Reference</div>
                <div className="text-xs text-slate-600 dark:text-slate-400">{finding.statutory_reference}</div>
              </div>
            )}
          </div>

          {/* Evidence Trail */}
          {finding.evidence.length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-2">
                Evidence Trail ({finding.evidence.length} item{finding.evidence.length > 1 ? 's' : ''})
              </div>
              <div className="space-y-2">
                {finding.evidence.map((ev, i) => (
                  <div key={i} className="bg-white/60 dark:bg-slate-900/60 rounded-xl border border-slate-200 dark:border-slate-700 p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 uppercase tracking-wider">
                        {ev.evidence_type}
                      </span>
                      <span className="text-[10px] text-slate-400">from</span>
                      <span className="text-[10px] font-mono text-slate-500">{ev.source_type}</span>
                    </div>
                    <blockquote className="text-xs text-slate-700 dark:text-slate-300 font-mono bg-slate-50 dark:bg-slate-900 rounded-lg p-2 border border-slate-200 dark:border-slate-800 leading-relaxed">
                      &ldquo;{ev.raw_text}&rdquo;
                    </blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type AnalysisStep = 'idle' | 'pipeline' | 'loading-report' | 'done' | 'error';

export default function CaseAnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params?.caseId as string;

  // Synchronous guard: prevents concurrent pipeline executions regardless of React
  // re-renders, rapid clicks, or double-clicks.
  const isRunningRef = useRef(false);

  const [report, setReport] = useState<ExplanationReport | null>(null);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [step, setStep] = useState<AnalysisStep>('idle');
  const [stepLabel, setStepLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string>('product');
  const [isDownloadingPdf, setIsDownloadingPdf] = useState<boolean>(false);

  const handleDownloadPdf = async () => {
    setIsDownloadingPdf(true);
    try {
      await downloadCaseReportPdf(caseId, report?.case_number);
    } catch (err: any) {
      alert(err?.message || 'Failed to download PDF report');
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const handleOpenHtml = async () => {
    try {
      await openCaseReportHtml(caseId);
    } catch (err: any) {
      alert(err?.message || 'Failed to open HTML report');
    }
  };

  const runFullAnalysis = useCallback(async () => {
    // Synchronous guard: if a run is already in progress (any path), bail out immediately.
    if (isRunningRef.current) return;
    isRunningRef.current = true;

    setError(null);
    setPipelineResult(null);
    try {
      setStep('pipeline');
      setStepLabel('Analyzing product information…');
      const pipeline = await runPipelineAnalysis(caseId);
      setPipelineResult(pipeline);

      setStep('loading-report');
      setStepLabel('Assembling explainability report…');
      const data = await fetchCaseExplanation(caseId);
      setReport(data);
      setStep('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
      setStep('error');
    } finally {
      // Always release the guard so the user can retry after an error.
      isRunningRef.current = false;
    }
  }, [caseId]);

  // Initial load: fetch existing explanation report if case was already analyzed.
  // If not analyzed, set step to 'idle' with STATUS: NOT ANALYZED.
  // NEVER automatically trigger runFullAnalysis!
  useEffect(() => {
    if (!caseId) return;
    setStep('loading-report');
    setStepLabel('Loading case details…');
    fetchCaseExplanation(caseId)
      .then((data) => {
        setReport(data);
        if (data?.risk_assessment) {
          setStep('done');
        } else {
          setStep('idle');
        }
      })
      .catch(() => {
        setStep('idle');
      });
  }, [caseId]);

  const sections = ['product', 'findings', 'risk', 'why', 'evidence'];
  const sectionLabels: Record<string, string> = {
    product: 'Product Information',
    findings: `Detected Findings ${report ? `(${report.total_findings})` : ''}`,
    risk: 'Risk Score',
    why: 'Why Flagged',
    evidence: 'Evidence Trail',
  };

  const riskCfg = report?.risk_assessment
    ? RISK_LEVEL_CONFIG[report.risk_assessment.risk_level as keyof typeof RISK_LEVEL_CONFIG] || RISK_LEVEL_CONFIG.LOW
    : null;

  const isAnalyzing = ['pipeline', 'loading-report'].includes(step);

  return (
    <div className="space-y-8 pb-16">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <button
            id="btn-back-cases"
            onClick={() => router.push('/dashboard/cases')}
            className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 mb-3 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Case Registry
          </button>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Case Analysis
          </h1>

          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {report?.case_number && (
              <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{report.case_number}</span>
            )}
            {/* Status indicator */}
            {isAnalyzing ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-0.5 rounded-full border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
                ANALYSIS IN PROGRESS
              </span>
            ) : step === 'error' ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-0.5 rounded-full border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                STATUS: ANALYSIS FAILED
              </span>
            ) : report?.risk_assessment ? (
              <>
                <span className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  ANALYSIS COMPLETE
                </span>
                <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${riskCfg?.color} ${riskCfg?.bg} ${riskCfg?.border}`}>
                  {report.risk_assessment.risk_level} RISK
                </span>
              </>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-0.5 rounded-full border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                STATUS: NOT ANALYZED
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            id="btn-evidence-viewer"
            onClick={() => router.push(`/dashboard/cases/${caseId}/evidence`)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 dark:border-emerald-700/60 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 shadow-sm transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Evidence Viewer
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-200 dark:bg-emerald-800 text-emerald-900 dark:text-emerald-200 font-bold">
              P13
            </span>
          </button>

          {/* Phase 15: Download Report Buttons */}
          <button
            id="btn-download-pdf-report"
            onClick={handleDownloadPdf}
            disabled={isDownloadingPdf || !report?.risk_assessment}
            className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-sm font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-750 shadow-sm transition-all disabled:opacity-50"
            title="Download Official Certified PDF Intelligence Report"
          >
            {isDownloadingPdf ? (
              <span className="w-4 h-4 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
            ) : (
              <svg className="w-4 h-4 text-rose-600 dark:text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            )}
            <span>PDF Report</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-300 font-bold">
              P15
            </span>
          </button>

          <button
            id="btn-view-html-report"
            onClick={handleOpenHtml}
            disabled={!report?.risk_assessment}
            className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
            title="Open Interactive HTML Dossier in New Tab"
          >
            <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            <span>HTML</span>
          </button>

          <button
            id="btn-run-analysis"
            onClick={runFullAnalysis}
            disabled={isAnalyzing || isRunningRef.current}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-600/20 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
          >
            {isAnalyzing ? (
              <>
                <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                <span>Analyzing product information...</span>
              </>
            ) : report?.risk_assessment ? (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>🔄 RE-ANALYZE</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>▶ RUN ANALYSIS</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {step === 'error' && (
        <div className="rounded-2xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/60 flex items-center justify-center flex-shrink-0 text-red-600 dark:text-red-400">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold text-red-800 dark:text-red-300">Analysis Failed</p>
              <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{error || 'An unexpected error occurred during case analysis.'}</p>
            </div>
          </div>
          <button
            id="btn-retry-analysis"
            onClick={runFullAnalysis}
            disabled={isAnalyzing || isRunningRef.current}
            className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-red-600 hover:bg-red-500 shadow-md shadow-red-600/20 disabled:opacity-50 transition-all flex items-center gap-1.5 flex-shrink-0"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Retry Analysis
          </button>
        </div>
      )}

      {/* ── Loading State ── */}
      {isAnalyzing && (
        <div className="rounded-2xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/60 dark:bg-emerald-950/30 p-8 flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full border-2 border-emerald-600 border-t-transparent animate-spin" />
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {step === 'pipeline' ? 'Analyzing product information…' : stepLabel}
          </p>
          <div className="flex gap-2">
            {(['pipeline', 'loading-report'] as AnalysisStep[]).map((s) => (
              <div key={s} className={`h-1.5 w-24 rounded-full transition-colors duration-500 ${
                step === s ? 'bg-emerald-500' :
                (['pipeline', 'loading-report'] as AnalysisStep[]).indexOf(step) >
                (['pipeline', 'loading-report'] as AnalysisStep[]).indexOf(s)
                  ? 'bg-emerald-300' : 'bg-slate-200 dark:bg-slate-700'
              }`} />
            ))}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {step === 'pipeline'
              ? 'OCR → Web Intelligence → Structuring → Deep Analysis → Consistency → Risk Assessment'
              : 'Building explainability report…'}
          </p>
        </div>
      )}

      {/* ── Idle / Not Analyzed State ── */}
      {step === 'idle' && !report?.risk_assessment && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/50 dark:bg-slate-900/40 p-12 flex flex-col items-center gap-5 text-center">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="max-w-md">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 mb-2">
                Status: Not Analyzed
              </span>
              <p className="text-base font-bold text-slate-800 dark:text-slate-200">
                Product compliance risk has not been analyzed yet
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">
                Click <strong>▶ RUN ANALYSIS</strong> to execute statutory label OCR, web intelligence verification, deep compliance checks, cross-source consistency audit, and risk scoring.
              </p>
            </div>
            <button
              id="btn-run-analysis-idle"
              onClick={runFullAnalysis}
              disabled={isAnalyzing || isRunningRef.current}
              className="flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-600/25 transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              ▶ RUN ANALYSIS
            </button>
          </div>

          {/* Product preview card if product summary exists */}
          {report?.product && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/80">
                <h2 className="text-sm font-black uppercase tracking-widest text-slate-700 dark:text-slate-300">
                  Product Details (Pending Statutory Audit)
                </h2>
              </div>
              <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {[
                  { label: 'Product Name', value: report.product.product_name },
                  { label: 'Brand', value: report.product.brand },
                  { label: 'Category', value: report.product.category?.replace(/_/g, ' ') },
                  { label: 'Manufacturer', value: report.product.manufacturer },
                  { label: 'FSSAI License No.', value: report.product.fssai_license_number },
                  { label: 'Case Number', value: report.case_number },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-1">{label}</div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {value || <span className="text-slate-400 italic">Not provided</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Pipeline Result Summary Banner ── */}
      {pipelineResult && step === 'done' && (
        <div className="rounded-2xl border border-emerald-200 dark:border-emerald-800 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/40 dark:to-teal-950/40 p-5 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-emerald-500 dark:bg-emerald-600 flex items-center justify-center shadow-sm flex-shrink-0">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-xs font-black uppercase tracking-wider text-emerald-900 dark:text-emerald-200">
                Analysis Pipeline Complete
              </p>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                {pipelineResult.case_number} &bull; {pipelineResult.total_findings} finding{pipelineResult.total_findings !== 1 ? 's' : ''} &bull; {pipelineResult.execution_duration_ms.toFixed(0)}ms
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {pipelineResult.risk_score !== null && (
              <div className="flex flex-col items-center px-4 py-2 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-800 shadow-sm">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Risk Score</span>
                <span className="text-2xl font-black tabular-nums text-slate-900 dark:text-white leading-none mt-0.5">
                  {Math.round((pipelineResult.risk_score || 0) * 100)}
                </span>
              </div>
            )}
            {pipelineResult.risk_level && (
              <div className={`px-4 py-2 rounded-xl border font-black text-sm uppercase tracking-widest ${
                pipelineResult.risk_level === 'HIGH'
                  ? 'bg-red-50 dark:bg-red-950/60 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                  : pipelineResult.risk_level === 'MEDIUM'
                  ? 'bg-amber-50 dark:bg-amber-950/60 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300'
                  : 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300'
              }`}>
                {pipelineResult.risk_level} Risk
              </div>
            )}
            {pipelineResult.priority && (
              <div className="px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-600 dark:text-slate-300 shadow-sm">
                {pipelineResult.priority.replace(/_/g, ' ')}
              </div>
            )}
          </div>
          {pipelineResult.errors.length > 0 && (
            <div className="w-full text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl px-3 py-2 mt-1">
              <strong>Partial results:</strong> {pipelineResult.errors.join('; ')}
            </div>
          )}
        </div>
      )}

      {/* ── Full Report ── */}
      {report && report.risk_assessment && step === 'done' && (

        <>
          {/* Section nav */}
          <div className="flex gap-1 flex-wrap">
            {sections.map((s) => (
              <button key={s} id={`nav-${s}`} onClick={() => setActiveSection(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  activeSection === s
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}>
                {sectionLabels[s]}
              </button>
            ))}
          </div>

          {/* ── PRODUCT INFORMATION ── */}
          {activeSection === 'product' && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/80">
                <h2 className="text-sm font-black uppercase tracking-widest text-slate-700 dark:text-slate-300">Product Information</h2>
              </div>
              <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {[
                  { label: 'Product Name', value: report.product.product_name },
                  { label: 'Brand', value: report.product.brand },
                  { label: 'Category', value: report.product.category?.replace(/_/g, ' ') },
                  { label: 'Manufacturer', value: report.product.manufacturer },
                  { label: 'FSSAI License No.', value: report.product.fssai_license_number },
                  { label: 'Case Number', value: report.case_number },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-1">{label}</div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {value || <span className="text-slate-400 italic">Not provided</span>}
                    </div>
                  </div>
                ))}
              </div>
              {/* Summary chips */}
              <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 flex flex-wrap gap-2">
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium self-center">Findings:</span>
                {Object.entries(report.findings_by_severity).map(([sev, count]) => {
                  const cfg = SEVERITY_CONFIG[sev as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.INFO;
                  return (
                    <span key={sev} className={`px-2.5 py-1 rounded-full text-xs font-bold border ${cfg.color} ${cfg.bg} ${cfg.border}`}>
                      {count} {cfg.label}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── DETECTED FINDINGS ── */}
          {activeSection === 'findings' && (
            <div className="space-y-3">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {report.total_findings} finding{report.total_findings !== 1 ? 's' : ''} detected. Sorted by severity. Click a finding to expand evidence.
              </p>
              {report.findings.length === 0 ? (
                <div className="rounded-2xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 p-8 text-center text-sm text-emerald-700 dark:text-emerald-400">
                  No findings detected for this case.
                </div>
              ) : (
                report.findings.map((f, i) => <FindingCard key={f.finding_id} finding={f} index={i} />)
              )}
            </div>
          )}

          {/* ── RISK SCORE ── */}
          {activeSection === 'risk' && (
            <div className="space-y-6">
              {!report.risk_assessment ? (
                <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center text-sm text-slate-500">
                  No risk assessment found. Run full analysis to generate a risk score.
                </div>
              ) : (
                <>
                  {/* Score display */}
                  <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-8">
                    <div className="flex flex-col sm:flex-row items-center gap-8">
                      <RiskGauge
                        score={report.risk_assessment.risk_score}
                        level={report.risk_assessment.risk_level}
                      />
                      <div className="flex-1 space-y-4">
                        <div>
                          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Confidence Score</div>
                          <ConfidenceBar value={report.risk_assessment.confidence_score} />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Data Completeness</div>
                          <ConfidenceBar value={report.risk_assessment.data_completeness_ratio} />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">Score Narrative</div>
                          <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{report.risk_assessment.score_explanation}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Disclaimer */}
                  <div className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 p-4">
                    <div className="flex gap-3">
                      <svg className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">{report.risk_assessment.disclaimer}</p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── WHY FLAGGED ── */}
          {activeSection === 'why' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/80">
                  <h2 className="text-sm font-black uppercase tracking-widest text-slate-700 dark:text-slate-300">
                    Why This Case Was Flagged
                  </h2>
                </div>
                <div className="p-6">
                  {report.why_flagged_summary.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">No high-priority flags detected.</p>
                  ) : (
                    <ol className="space-y-3">
                      {report.why_flagged_summary.map((reason, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 text-xs font-black flex items-center justify-center">
                            {i + 1}
                          </span>
                          <p className="text-sm text-slate-700 dark:text-slate-300 pt-0.5">{reason}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>

              {/* Contributing factors */}
              {report.risk_assessment && report.risk_assessment.contributing_factors.length > 0 && (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden">
                  <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/80">
                    <h3 className="text-sm font-black uppercase tracking-widest text-slate-700 dark:text-slate-300">Contributing Dimensions</h3>
                  </div>
                  <div className="p-6 space-y-4">
                    {report.risk_assessment.contributing_factors
                      .filter(f => f.finding_count > 0)
                      .sort((a, b) => b.weighted_contribution - a.weighted_contribution)
                      .map((factor) => (
                        <div key={factor.dimension} className="flex items-center gap-4">
                          <div className="w-40 flex-shrink-0">
                            <div className="text-xs font-bold text-slate-700 dark:text-slate-300">
                              {factor.dimension.replace(/_/g, ' ')}
                            </div>
                            <div className="text-[10px] text-slate-400">
                              {factor.finding_count} finding{factor.finding_count > 1 ? 's' : ''} · max {factor.max_severity}
                            </div>
                          </div>
                          <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-700"
                              style={{ width: `${Math.round(factor.weighted_contribution * 100 / Math.max(...report.risk_assessment!.contributing_factors.map(f => f.weighted_contribution), 0.01) * 100)}%` }}
                            />
                          </div>
                          <div className="w-12 text-right text-xs font-mono text-slate-500">
                            {(factor.weighted_contribution * 100).toFixed(1)}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── EVIDENCE TRAIL ── */}
          {activeSection === 'evidence' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/40 dark:to-slate-900 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-600 text-white uppercase font-mono">Phase 13</span>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">Statutory Evidence Management System</h3>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                    Explore the complete 4-tier chain of custody (Finding $\rightarrow$ Why Flagged $\rightarrow$ Source $\rightarrow$ Original Evidence), SHA-256 hashes, and real-time cryptographic audit.
                  </p>
                </div>
                <button
                  id="btn-open-full-evidence"
                  onClick={() => router.push(`/dashboard/cases/${caseId}/evidence`)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md transition-all flex items-center gap-1.5 flex-shrink-0"
                >
                  Open Evidence Viewer
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400">{report.provenance_note}</p>
              {report.findings.filter(f => f.evidence.length > 0).length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-700 p-8 text-center text-sm text-slate-500">
                  No stored evidence items available for this case.
                </div>
              ) : (
                report.findings
                  .filter(f => f.evidence.length > 0)
                  .map((finding) => (
                    <div key={finding.finding_id} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden">
                      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
                        <SeverityBadge severity={finding.severity} />
                        <span className="text-sm font-bold text-slate-800 dark:text-slate-200">{finding.finding_title}</span>
                      </div>
                      <div className="p-4 space-y-2">
                        {finding.evidence.map((ev, i) => (
                          <div key={i} className="rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 uppercase">
                                {ev.evidence_type}
                              </span>
                              <span className="text-[10px] text-slate-400">·</span>
                              <span className="text-[10px] font-mono text-slate-500">{ev.source_type}</span>
                            </div>
                            <blockquote className="text-xs font-mono text-slate-700 dark:text-slate-300 leading-relaxed">
                              &ldquo;{ev.raw_text}&rdquo;
                            </blockquote>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
