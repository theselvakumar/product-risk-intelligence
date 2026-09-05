'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  fetchCaseEvidencePackage,
  verifyEvidenceIntegrity,
  CaseEvidencePackage,
  FindingEvidenceBundle,
  EvidenceRecord,
  EvidenceIntegrityCheckResult,
} from '@/services/api';

const SEVERITY_THEME: Record<string, { badge: string; border: string; bg: string; text: string; dot: string }> = {
  CRITICAL: { badge: 'bg-red-500/15 text-red-500 border-red-500/30', border: 'border-red-500/30', bg: 'bg-red-500/5', text: 'text-red-400', dot: 'bg-red-500' },
  HIGH:     { badge: 'bg-orange-500/15 text-orange-400 border-orange-500/30', border: 'border-orange-500/30', bg: 'bg-orange-500/5', text: 'text-orange-400', dot: 'bg-orange-400' },
  MEDIUM:   { badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30', border: 'border-amber-500/30', bg: 'bg-amber-500/5', text: 'text-amber-400', dot: 'bg-amber-400' },
  LOW:      { badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', border: 'border-emerald-500/30', bg: 'bg-emerald-500/5', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  INFO:     { badge: 'bg-blue-500/15 text-blue-400 border-blue-500/30', border: 'border-blue-500/30', bg: 'bg-blue-500/5', text: 'text-blue-400', dot: 'bg-blue-400' },
};

export default function CaseEvidenceViewerPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params?.caseId as string;

  const [evidencePackage, setEvidencePackage] = useState<CaseEvidencePackage | null>(null);
  const [auditResult, setAuditResult] = useState<EvidenceIntegrityCheckResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [auditing, setAuditing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters & Tabs
  const [activeTab, setActiveTab] = useState<'lineage' | 'repository' | 'audit'>('lineage');
  const [repoSubTab, setRepoSubTab] = useState<'urls' | 'images' | 'ocr' | 'submitted' | 'extracted'>('images');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const pkg = await fetchCaseEvidencePackage(caseId);
      setEvidencePackage(pkg);
      // Automatically trigger initial integrity audit
      try {
        const audit = await verifyEvidenceIntegrity(caseId);
        setAuditResult(audit);
      } catch {
        // Fallback gracefully if verify hasn't been cached
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load evidence package');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRunAudit = async () => {
    if (!caseId) return;
    setAuditing(true);
    try {
      const res = await verifyEvidenceIntegrity(caseId);
      setAuditResult(res);
      setActiveTab('audit');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Integrity audit failed');
    } finally {
      setAuditing(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Filtered finding bundles
  const filteredBundles = (evidencePackage?.finding_bundles || []).filter((b) => {
    if (selectedSeverity !== 'ALL' && b.severity !== selectedSeverity) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = b.finding_title.toLowerCase().includes(q);
      const matchWhy = b.why_flagged.toLowerCase().includes(q);
      const matchSource = b.source.toLowerCase().includes(q);
      const matchEv = b.primary_evidence.some((e) => (e.content_text || '').toLowerCase().includes(q));
      if (!matchTitle && !matchWhy && !matchSource && !matchEv) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-6 lg:p-8 space-y-6">
      {/* ── Breadcrumb & Top Bar ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <nav className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-1">
            <button onClick={() => router.push('/dashboard/cases')} className="hover:text-emerald-400 transition-colors">
              Case Registry
            </button>
            <span>/</span>
            <button onClick={() => router.push(`/dashboard/cases/${caseId}/analysis`)} className="hover:text-emerald-400 transition-colors">
              {evidencePackage?.case_number || 'Case Detail'}
            </button>
            <span>/</span>
            <span className="text-emerald-400 font-bold">Evidence Management Package</span>
          </nav>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </span>
              Statutory Evidence Viewer
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 font-mono font-semibold">
              PHASE 13 COMPLIANT
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Product: <strong className="text-slate-200">{evidencePackage?.product_name || 'Loading…'}</strong> | Case:{' '}
            <span className="font-mono text-emerald-400">{evidencePackage?.case_number}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            id="btn-back-to-analysis"
            onClick={() => router.push(`/dashboard/cases/${caseId}/analysis`)}
            className="px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300 transition-all flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 15l-3-3m0 0l3-3m-3 3h8M3 12a9 9 0 1118 0 9 9 0 01-18 0z" />
            </svg>
            Case Analysis View
          </button>

          <button
            id="btn-verify-integrity"
            onClick={handleRunAudit}
            disabled={auditing || loading}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-900/30 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {auditing ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Auditing Cryptographic Hashes…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                Audit Evidence Integrity
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Statutory Warning & AI Separation Policy Banner ── */}
      <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 p-4 text-xs text-slate-300 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex-shrink-0 mt-0.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">
              Statutory Chain of Custody &amp; Strict AI Segregation Policy
            </p>
            <p className="text-slate-300 mt-0.5 leading-relaxed">
              Every finding is immutably anchored to verified primary physical evidence (URLs, Images, OCR tokens, Submitted Text).
              AI-generated statements are strictly quarantined in separate analytical modules with mandatory disclaimers and never presented as primary source facts.
            </p>
          </div>
        </div>

        {auditResult && (
          <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-emerald-500/30 flex-shrink-0">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-mono text-emerald-400 font-bold text-xs">
              Integrity Score: {auditResult.integrity_score}%
            </span>
          </div>
        )}
      </div>

      {/* ── Metric Summary Cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Total Evidence', value: evidencePackage?.total_evidence_records || 0, icon: '📦', color: 'text-white' },
          { label: 'Product URLs', value: evidencePackage?.url_evidence.length || 0, icon: '🌐', color: 'text-blue-400' },
          { label: 'Images Stored', value: evidencePackage?.image_evidence.length || 0, icon: '📷', color: 'text-emerald-400' },
          { label: 'OCR Snippets', value: evidencePackage?.ocr_evidence.length || 0, icon: '🔍', color: 'text-cyan-400' },
          { label: 'Submitted Text', value: evidencePackage?.submitted_text_evidence.length || 0, icon: '📝', color: 'text-amber-400' },
          {
            label: 'Finding Coverage',
            value: `${evidencePackage?.coverage_percentage || 100}%`,
            icon: '🛡️',
            color: 'text-emerald-300',
          },
        ].map((card, idx) => (
          <div key={idx} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
              <span>{card.label}</span>
              <span>{card.icon}</span>
            </div>
            <div className={`text-xl font-black mt-2 ${card.color}`}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* ── Main Navigation Tabs ── */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-slate-800 pb-2">
        <div className="flex gap-2">
          <button
            id="tab-lineage"
            onClick={() => setActiveTab('lineage')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'lineage'
                ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/20'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>Finding $\rightarrow$ Evidence Chain</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-white/20 font-mono">
              {evidencePackage?.finding_bundles.length || 0}
            </span>
          </button>

          <button
            id="tab-repository"
            onClick={() => setActiveTab('repository')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'repository'
                ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/20'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>Evidence Repository Browser</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-white/20 font-mono">
              {evidencePackage?.total_evidence_records || 0}
            </span>
          </button>

          <button
            id="tab-audit"
            onClick={() => setActiveTab('audit')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'audit'
                ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/20'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>Cryptographic &amp; Statutory Audit</span>
            {auditResult && (
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
            )}
          </button>
        </div>

        {activeTab === 'lineage' && (
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Search findings or evidence text…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-56 font-sans"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-2 text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-emerald-500 font-mono"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        )}
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="rounded-2xl border border-red-500/40 bg-red-950/40 p-4 text-xs text-red-300 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-white font-bold ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* ── Loading Spinner ── */}
      {loading && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-16 flex flex-col items-center justify-center gap-4 text-center">
          <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Loading statutory evidence package…</p>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: FINDING -> EVIDENCE CHAIN (STATUTORY LINEAGE)                 */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {!loading && activeTab === 'lineage' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              Showing {filteredBundles.length} statutory findings with linked evidence
            </span>
            <span className="font-mono text-emerald-400">
              100% Verified Finding-to-Evidence Linkage
            </span>
          </div>

          {filteredBundles.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center text-xs text-slate-500">
              No finding evidence bundles matched your search criteria.
            </div>
          ) : (
            filteredBundles.map((bundle, idx) => {
              const theme = SEVERITY_THEME[bundle.severity] || SEVERITY_THEME.INFO;
              return (
                <div
                  key={bundle.finding_id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/50 hover:bg-slate-900/80 transition-all overflow-hidden"
                >
                  {/* Finding Header */}
                  <div className="p-4 border-b border-slate-800/80 bg-slate-900/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold text-slate-500">#{idx + 1}</span>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${theme.badge} flex items-center gap-1.5`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${theme.dot}`} />
                        {bundle.severity}
                      </span>
                      <h2 className="text-sm font-bold text-white">{bundle.finding_title}</h2>
                    </div>

                    <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                      {bundle.rule_code && (
                        <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                          {bundle.rule_code}
                        </span>
                      )}
                      {bundle.statutory_reference && (
                        <span className="bg-slate-800/60 px-2 py-0.5 rounded text-slate-400">
                          {bundle.statutory_reference}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 4-Step Hierarchy Body */}
                  <div className="p-5 space-y-4">
                    {/* Step 1 & 2: WHY FLAGGED */}
                    <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-3.5 flex items-start gap-3">
                      <div className="p-1 rounded bg-amber-500/20 text-amber-400 flex-shrink-0 mt-0.5">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-amber-400 mb-0.5 flex items-center gap-1">
                          <span>WHY FLAGGED</span>
                          <span className="text-slate-500">↓</span>
                        </div>
                        <p className="text-xs text-slate-200 leading-relaxed font-medium">
                          {bundle.why_flagged}
                        </p>
                      </div>
                    </div>

                    {/* Step 3: SOURCE */}
                    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 flex items-start gap-3">
                      <div className="p-1 rounded bg-blue-500/20 text-blue-400 flex-shrink-0 mt-0.5">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-1 flex items-center gap-1">
                          <span>SOURCE ORIGIN</span>
                          <span className="text-slate-500">↓</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300 font-mono">
                          <span className="px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/50 text-blue-300 font-bold">
                            {bundle.source}
                          </span>
                          {bundle.source_metadata?.platform && (
                            <span>Platform: <strong className="text-white">{bundle.source_metadata.platform}</strong></span>
                          )}
                          {bundle.source_metadata?.seller && (
                            <span>Seller: <strong className="text-white">{bundle.source_metadata.seller}</strong></span>
                          )}
                          {bundle.source_metadata?.timestamp && (
                            <span className="text-slate-500">
                              Captured: {new Date(bundle.source_metadata.timestamp).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Step 4: ORIGINAL EVIDENCE */}
                    <div className="space-y-2">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-emerald-400 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          ORIGINAL PRIMARY EVIDENCE ({bundle.primary_evidence.length} artifact{bundle.primary_evidence.length > 1 ? 's' : ''})
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          Non-AI Physical Record
                        </span>
                      </div>

                      <div className="grid grid-cols-1 gap-2.5">
                        {bundle.primary_evidence.map((ev, eIdx) => (
                          <div
                            key={eIdx}
                            className="rounded-xl border border-emerald-500/30 bg-emerald-950/10 p-3.5 space-y-2"
                          >
                            <div className="flex items-center justify-between text-xs">
                              <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                                  {ev.evidence_type}
                                </span>
                                <span className="text-[11px] font-mono text-slate-400">
                                  via {ev.source_type}
                                </span>
                              </div>

                              {ev.sha256_hash && (
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] text-slate-500 font-mono">SHA-256:</span>
                                  <button
                                    onClick={() => copyToClipboard(ev.sha256_hash!, `hash-${ev.record_id}`)}
                                    className="font-mono text-[10px] text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-emerald-500/30 hover:bg-slate-900 transition-colors"
                                  >
                                    {copiedHash === `hash-${ev.record_id}` ? '✓ Copied' : `${ev.sha256_hash.substring(0, 12)}…`}
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Verbatim Content */}
                            {ev.content_text && (
                              <blockquote className="rounded-lg bg-slate-950/80 p-3 text-xs text-slate-200 font-mono border border-slate-800 leading-relaxed break-words">
                                &ldquo;{ev.content_text}&rdquo;
                              </blockquote>
                            )}

                            {/* Image URI */}
                            {ev.content_uri && (
                              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
                                <span className="truncate max-w-md text-emerald-300">
                                  URI: {ev.content_uri}
                                </span>
                                {ev.capture_timestamp && (
                                  <span className="text-slate-500">
                                    {new Date(ev.capture_timestamp).toLocaleString()}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Step 5: STRICTLY QUARANTINED AI ANALYSIS OBSERVATIONS */}
                    {bundle.ai_analysis_notes.length > 0 && (
                      <div className="rounded-xl border border-purple-500/30 bg-purple-950/10 p-3.5 space-y-2 mt-3">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 uppercase tracking-wider font-mono">
                              AI ANALYSIS OBSERVATION
                            </span>
                            <span className="text-[11px] text-purple-400 font-medium">
                              (Derived Analytical Deduction — Not Primary Source Evidence)
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400">
                            Confidence: {Math.round((bundle.ai_analysis_notes[0].confidence || 0.85) * 100)}%
                          </span>
                        </div>

                        <p className="text-xs text-slate-300 leading-relaxed font-sans italic bg-slate-950/50 p-2.5 rounded-lg border border-purple-900/40">
                          {bundle.ai_analysis_notes[0].content_text}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: EVIDENCE REPOSITORY BROWSER (ALL STORED ARTIFACTS)           */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {!loading && activeTab === 'repository' && evidencePackage && (
        <div className="space-y-4">
          {/* Sub-nav */}
          <div className="flex gap-2 border-b border-slate-800 pb-2">
            {[
              { id: 'images', label: `Images (${evidencePackage.image_evidence.length})` },
              { id: 'urls', label: `Product URLs (${evidencePackage.url_evidence.length})` },
              { id: 'ocr', label: `OCR Text (${evidencePackage.ocr_evidence.length})` },
              { id: 'submitted', label: `Submitted Text (${evidencePackage.submitted_text_evidence.length})` },
              { id: 'extracted', label: `Extracted Data (${evidencePackage.extracted_data_evidence.length})` },
            ].map((st) => (
              <button
                key={st.id}
                onClick={() => setRepoSubTab(st.id as any)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                  repoSubTab === st.id
                    ? 'bg-slate-800 text-emerald-400 border border-emerald-500/40'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          {/* Sub-tab: Images */}
          {repoSubTab === 'images' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {evidencePackage.image_evidence.length === 0 ? (
                <div className="col-span-full rounded-2xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                  No images registered for this case.
                </div>
              ) : (
                evidencePackage.image_evidence.map((img, i) => (
                  <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
                    <div className="aspect-video rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-600 font-mono text-xs">
                      {img.content_uri ? (
                        <div className="flex flex-col items-center gap-1">
                          <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          <span className="text-[10px] text-slate-400 max-w-[200px] truncate">{img.content_uri}</span>
                        </div>
                      ) : (
                        'No Image Preview Available'
                      )}
                    </div>

                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase text-slate-400">Type</span>
                        <span className="font-mono text-emerald-400">{img.metadata?.image_type || 'PACKAGING'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase text-slate-400">MIME Type</span>
                        <span className="font-mono text-slate-300">{img.metadata?.mime_type || 'image/jpeg'}</span>
                      </div>
                      {img.sha256_hash && (
                        <div>
                          <div className="text-[10px] font-bold uppercase text-slate-400 mb-0.5">SHA-256 Checksum</div>
                          <button
                            onClick={() => copyToClipboard(img.sha256_hash!, `img-${img.record_id}`)}
                            className="w-full text-left font-mono text-[10px] text-slate-300 bg-slate-950 p-1.5 rounded border border-slate-800 hover:border-emerald-500 truncate"
                          >
                            {copiedHash === `img-${img.record_id}` ? '✓ Copied to clipboard' : img.sha256_hash}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Sub-tab: URLs */}
          {repoSubTab === 'urls' && (
            <div className="space-y-3">
              {evidencePackage.url_evidence.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                  No URL evidence registered for this case.
                </div>
              ) : (
                evidencePackage.url_evidence.map((u, i) => (
                  <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800 font-mono text-[10px] font-bold">
                        {u.source_type}
                      </span>
                      {u.capture_timestamp && (
                        <span className="font-mono text-slate-500 text-[10px]">
                          {new Date(u.capture_timestamp).toLocaleString()}
                        </span>
                      )}
                    </div>
                    {u.content_uri && (
                      <a
                        href={u.content_uri}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-mono text-emerald-400 hover:underline block break-all"
                      >
                        {u.content_uri} ↗
                      </a>
                    )}
                    {u.content_text && u.content_text !== u.content_uri && (
                      <blockquote className="rounded-lg bg-slate-950 p-2.5 text-xs text-slate-300 font-mono border border-slate-800">
                        {u.content_text}
                      </blockquote>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Sub-tab: OCR Text */}
          {repoSubTab === 'ocr' && (
            <div className="space-y-3">
              {evidencePackage.ocr_evidence.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                  No OCR text extracts registered for this case.
                </div>
              ) : (
                evidencePackage.ocr_evidence.map((o, i) => (
                  <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 text-[10px] font-bold">
                        ZONE: {o.metadata?.zone_type || 'FULL_PACK'}
                      </span>
                      {o.confidence && (
                        <span className="text-slate-400 text-[10px]">
                          Confidence: {Math.round(o.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <blockquote className="rounded-lg bg-slate-950 p-3 text-xs text-slate-200 font-mono border border-slate-800 whitespace-pre-wrap leading-relaxed">
                      {o.content_text || 'No text extracted'}
                    </blockquote>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Sub-tab: Submitted Text */}
          {repoSubTab === 'submitted' && (
            <div className="space-y-3">
              {evidencePackage.submitted_text_evidence.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                  No officer-submitted text registered for this case.
                </div>
              ) : (
                evidencePackage.submitted_text_evidence.map((s, i) => (
                  <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-200 text-xs font-mono">
                        {s.metadata?.label || 'Officer Submission'}
                      </span>
                      {s.capture_timestamp && (
                        <span className="font-mono text-slate-500 text-[10px]">
                          {new Date(s.capture_timestamp).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <blockquote className="rounded-lg bg-slate-950 p-3 text-xs text-slate-300 font-mono border border-slate-800 whitespace-pre-wrap leading-relaxed">
                      {s.content_text}
                    </blockquote>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Sub-tab: Extracted Data */}
          {repoSubTab === 'extracted' && (
            <div className="space-y-3">
              {evidencePackage.extracted_data_evidence.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                  No structured extracted data registered for this case.
                </div>
              ) : (
                evidencePackage.extracted_data_evidence.map((ed, i) => (
                  <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="text-xs font-bold text-slate-300 font-mono">{ed.source_type}</div>
                    <div className="rounded-lg bg-slate-950 p-3 text-xs text-slate-200 font-mono border border-slate-800">
                      {ed.content_text || JSON.stringify(ed.metadata, null, 2)}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: CRYPTOGRAPHIC & STATUTORY AUDIT REPORT                       */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      {!loading && activeTab === 'audit' && (
        <div className="space-y-6">
          {!auditResult ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center text-xs text-slate-500">
              No audit report generated yet. Click &ldquo;Audit Evidence Integrity&rdquo; above to execute the verification suite.
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-lg font-black text-white">Statutory Integrity Audit Report</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Case: <span className="font-mono text-emerald-400">{auditResult.case_number}</span> | Audit Timestamp:{' '}
                    <span className="font-mono text-slate-300">{new Date(auditResult.verified_at).toLocaleString()}</span>
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Composite Score</div>
                    <div className="text-2xl font-black text-emerald-400">{auditResult.integrity_score}/100</div>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    PASS
                  </span>
                </div>
              </div>

              {/* Audit Checklist Items */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-white">Finding Linkage Coverage</span>
                    {auditResult.all_findings_linked ? (
                      <span className="text-emerald-400">✓ PASS (100%)</span>
                    ) : (
                      <span className="text-amber-400">⚠ PARTIAL</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    {auditResult.findings_with_evidence} of {auditResult.total_findings} findings are strictly linked to original primary evidence.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-white">Strict AI Segregation</span>
                    {auditResult.ai_separation_verified ? (
                      <span className="text-emerald-400">✓ PASS (0 Breaches)</span>
                    ) : (
                      <span className="text-red-400">✗ BREACH DETECTED</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    {auditResult.unmarked_ai_items_found} AI statements detected in primary evidence repositories.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-white">Cryptographic Checksums (SHA-256)</span>
                    {auditResult.hash_verification_passed ? (
                      <span className="text-emerald-400">✓ PASS</span>
                    ) : (
                      <span className="text-red-400">✗ FAIL</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    {auditResult.valid_hashes} of {auditResult.total_hashed_items} hashed files verified with valid 64-character SHA-256 signatures.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-white">Timestamp Traceability</span>
                    {auditResult.timestamps_valid ? (
                      <span className="text-emerald-400">✓ PASS</span>
                    ) : (
                      <span className="text-amber-400">⚠ INCOMPLETE</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    All evidentiary records document chronological capture and submission timestamps.
                  </p>
                </div>
              </div>

              {/* Detailed Breakdown List */}
              <div className="space-y-2">
                <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Audit Trail Verification Logs</div>
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1.5 font-mono text-xs text-slate-300">
                  {auditResult.verification_details.map((line, lIdx) => (
                    <div key={lIdx} className="leading-relaxed">
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
