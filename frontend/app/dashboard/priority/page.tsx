'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import {
  PriorityQueueItem,
  PriorityQueueResponse,
  fetchPriorityQueue,
  startCaseReview,
  submitCaseReview,
  updateCaseStatus,
  downloadCaseReportPdf,
} from '@/services/api';

const RISK_LEVEL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  CRITICAL: {
    bg: 'bg-red-500/10 dark:bg-red-500/20',
    text: 'text-red-700 dark:text-red-400',
    border: 'border-red-200 dark:border-red-800',
  },
  HIGH: {
    bg: 'bg-orange-500/10 dark:bg-orange-500/20',
    text: 'text-orange-700 dark:text-orange-400',
    border: 'border-orange-200 dark:border-orange-800',
  },
  MEDIUM: {
    bg: 'bg-amber-500/10 dark:bg-amber-500/20',
    text: 'text-amber-700 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
  },
  LOW: {
    bg: 'bg-emerald-500/10 dark:bg-emerald-500/20',
    text: 'text-emerald-700 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800',
  },
};

const STATUS_BADGES: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  PRIORITY_REVIEW: {
    label: 'Priority Review',
    bg: 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900',
    text: 'text-rose-700 dark:text-rose-400',
    dot: 'bg-rose-500 animate-pulse',
  },
  STANDARD_REVIEW: {
    label: 'Standard Review',
    bg: 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900',
    text: 'text-blue-700 dark:text-blue-400',
    dot: 'bg-blue-500',
  },
  UNDER_REVIEW: {
    label: 'Under Review',
    bg: 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900',
    text: 'text-amber-700 dark:text-amber-400',
    dot: 'bg-amber-500 animate-ping',
  },
  REVIEW_COMPLETED: {
    label: 'Review Completed',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900',
    text: 'text-emerald-700 dark:text-emerald-400',
    dot: 'bg-emerald-500',
  },
  ANALYSIS_COMPLETE: {
    label: 'Analysis Complete',
    bg: 'bg-purple-50 dark:bg-purple-950/40 border-purple-200 dark:border-purple-900',
    text: 'text-purple-700 dark:text-purple-400',
    dot: 'bg-purple-500',
  },
  RESOLVED: {
    label: 'Resolved',
    bg: 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700',
    text: 'text-slate-700 dark:text-slate-300',
    dot: 'bg-slate-400',
  },
  CLOSED: {
    label: 'Closed',
    bg: 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700',
    text: 'text-slate-600 dark:text-slate-400',
    dot: 'bg-slate-400',
  },
};

export default function PriorityReviewPage() {
  const [data, setData] = useState<PriorityQueueResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search & Sort states
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRisk, setSelectedRisk] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('risk_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Review modal states
  const [activeReviewCase, setActiveReviewCase] = useState<PriorityQueueItem | null>(null);
  const [reviewAction, setReviewAction] = useState<string>('ISSUE_SECTION_32_NOTICE');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [targetStatus, setTargetStatus] = useState<string>('UNDER_REVIEW');
  const [statutoryDays, setStatutoryDays] = useState<number>(14);
  const [isSubmittingReview, setIsSubmittingReview] = useState<boolean>(false);

  // Status update modal states
  const [activeStatusCase, setActiveStatusCase] = useState<PriorityQueueItem | null>(null);
  const [newStatusValue, setNewStatusValue] = useState<string>('UNDER_REVIEW');
  const [statusReason, setStatusReason] = useState<string>('');
  const [isSubmittingStatus, setIsSubmittingStatus] = useState<boolean>(false);

  // Notification / Feedback banner
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPriorityQueue({
        search: searchQuery.trim() || undefined,
        status: selectedStatus !== 'ALL' ? selectedStatus : undefined,
        risk_level: selectedRisk !== 'ALL' ? selectedRisk : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: 50,
      });
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load priority review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [selectedRisk, selectedStatus, sortBy, sortOrder]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadQueue();
  };

  const handleStartReview = async (item: PriorityQueueItem) => {
    try {
      await startCaseReview(item.case_id);
      setActionSuccess(`Case #${item.case_number} transitioned to UNDER_REVIEW. Assigned to your badge.`);
      loadQueue();
    } catch (err: any) {
      alert(err?.message || 'Failed to start case review');
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeReviewCase) return;
    if (!reviewNotes.trim()) {
      alert('Statutory review notes and reason are mandatory.');
      return;
    }

    setIsSubmittingReview(true);
    try {
      await submitCaseReview(activeReviewCase.case_id, {
        action: reviewAction,
        notes: reviewNotes.trim(),
        target_status: targetStatus,
        statutory_deadline_days: statutoryDays > 0 ? statutoryDays : undefined,
      });
      setActionSuccess(`Authority review action recorded for Case #${activeReviewCase.case_number}. Audit entry created.`);
      setActiveReviewCase(null);
      setReviewNotes('');
      loadQueue();
    } catch (err: any) {
      alert(err?.message || 'Failed to submit review');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const handleSubmitStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeStatusCase) return;

    setIsSubmittingStatus(true);
    try {
      await updateCaseStatus(activeStatusCase.case_id, {
        status: newStatusValue,
        reason: statusReason.trim() || undefined,
      });
      setActionSuccess(`Status for Case #${activeStatusCase.case_number} updated to ${newStatusValue}.`);
      setActiveStatusCase(null);
      setStatusReason('');
      loadQueue();
    } catch (err: any) {
      alert(err?.message || 'Failed to update status');
    } finally {
      setIsSubmittingStatus(false);
    }
  };

  const items = data?.items || [];

  return (
    <div className="space-y-6 pb-12">
      {/* Statutory Header & Disclaimer */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-100 dark:bg-rose-900/50 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800 mb-2">
            <span className="w-2 h-2 rounded-full bg-rose-600 animate-pulse"></span>
            Statutory Surveillance Desk (Phase 14)
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Priority Review Queue & Case Management
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
            High-risk product dossiers triaged automatically based on severe non-compliance indicators, toxic adulterants, and prohibited therapeutic claims under the FSS Act, 2006.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadQueue()}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 shadow-sm transition-all flex items-center gap-2"
          >
            <svg
              className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-600' : 'text-slate-500'}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Authority Separation Legal Mandate Alert */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-amber-500/20 text-amber-700 dark:text-amber-400 shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div className="text-xs space-y-1">
            <div className="font-bold text-amber-900 dark:text-amber-100 flex items-center gap-2">
              <span>STATUTORY GOVERNANCE DIRECTIVE: HUMAN AUTHORITY SUPREMACY</span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-200 dark:bg-amber-900 text-amber-800 dark:text-amber-300">Mandatory</span>
            </div>
            <p className="text-amber-800/90 dark:text-amber-300/90 leading-relaxed">
              AI-generated scores, findings, and triage routes are advisory intelligence instruments only. <strong>AI algorithms cannot automatically penalize, close, or prosecute cases.</strong> Every statutory action (Section 32 Improvement Notice, sampling seizure, or case dismissal) requires sovereign officer review with full immutable audit logging.
            </p>
          </div>
        </div>
      </div>

      {/* Success Notification */}
      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-800 dark:text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-slate-400 hover:text-slate-600">
            &times;
          </button>
        </div>
      )}

      {/* Metrics Counter Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Urgent Cases (P1)</span>
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-rose-600 dark:text-rose-400">{data?.urgent_count ?? 0}</span>
            <span className="text-xs text-slate-400">Critical priority</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">High Risk (P2)</span>
            <span className="w-2 h-2 rounded-full bg-orange-500"></span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-orange-600 dark:text-orange-400">{data?.high_count ?? 0}</span>
            <span className="text-xs text-slate-400">Priority review</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Standard Stream</span>
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-blue-600 dark:text-blue-400">{data?.standard_count ?? 0}</span>
            <span className="text-xs text-slate-400">Medium / Low</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Total Queue</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900 dark:text-white">{data?.total ?? 0}</span>
            <span className="text-xs text-slate-400">Dockets</span>
          </div>
        </div>
      </div>

      {/* Control Bar: Search, Risk Filter, Status Filter, Sort */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Case ID, Product, Brand, License..."
              className="w-full pl-9 pr-20 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 text-slate-900 dark:text-white placeholder-slate-400"
            />
            <svg
              className="w-4 h-4 text-slate-400 absolute left-3 top-2.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <button
              type="submit"
              className="absolute right-1.5 top-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold text-white bg-slate-900 dark:bg-slate-700 hover:bg-slate-800 transition-colors"
            >
              Search
            </button>
          </form>

          {/* Sort Controls */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-slate-400">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-2.5 py-1.5 rounded-xl text-xs bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 font-medium"
            >
              <option value="risk_score">Risk Score</option>
              <option value="created_at">Submission Date</option>
              <option value="confidence_score">Confidence Score</option>
              <option value="case_number">Case ID</option>
            </select>

            <button
              onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
              className="p-1.5 rounded-xl text-xs bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100"
              title={`Sort ${sortOrder === 'desc' ? 'Ascending' : 'Descending'}`}
            >
              <svg className={`w-4 h-4 transform ${sortOrder === 'asc' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Filter Chips */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 dark:border-slate-800">
          {/* Risk Filters */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-slate-400 mr-1 font-medium">Risk Level:</span>
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((risk) => (
              <button
                key={risk}
                onClick={() => setSelectedRisk(risk)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  selectedRisk === risk
                    ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm'
                    : 'bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
                }`}
              >
                {risk === 'ALL' ? 'All Risks' : risk}
              </button>
            ))}
          </div>

          {/* Status Filters */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-slate-400 mr-1 font-medium">Status:</span>
            {[
              { id: 'ALL', label: 'All' },
              { id: 'PRIORITY_REVIEW', label: 'Priority Review' },
              { id: 'UNDER_REVIEW', label: 'Under Review' },
              { id: 'STANDARD_REVIEW', label: 'Standard Review' },
              { id: 'REVIEW_COMPLETED', label: 'Completed' },
            ].map((st) => (
              <button
                key={st.id}
                onClick={() => setSelectedStatus(st.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  selectedStatus === st.id
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Queue Table */}
      <div className="bg-white dark:bg-slate-800/80 border border-slate-200/80 dark:border-slate-700/80 rounded-2xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <div className="inline-block w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="mt-3 text-xs text-slate-500">Loading priority surveillance records...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-500 text-xs font-medium">
            <p>{error}</p>
            <button
              onClick={() => loadQueue()}
              className="mt-3 px-3 py-1.5 bg-rose-50 dark:bg-rose-950/50 rounded-lg text-rose-600 text-xs font-bold"
            >
              Try Again
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs">
            <svg className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="font-semibold text-slate-600 dark:text-slate-300">No cases match the selected filters</p>
            <p className="mt-1">Try broadening your search or resetting the risk and status criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700/60 bg-slate-50/50 dark:bg-slate-900/30 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  <th className="py-3.5 px-4">Case ID</th>
                  <th className="py-3.5 px-4">Product & Category</th>
                  <th className="py-3.5 px-4">Risk Score</th>
                  <th className="py-3.5 px-4">Risk Level</th>
                  <th className="py-3.5 px-4">Confidence</th>
                  <th className="py-3.5 px-4">Submission Date</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Authority Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/40 text-xs">
                {items.map((item) => {
                  const riskStyle = RISK_LEVEL_COLORS[item.risk_level || 'LOW'] || RISK_LEVEL_COLORS.LOW;
                  const statusStyle = STATUS_BADGES[item.status] || STATUS_BADGES.PRIORITY_REVIEW;
                  const scorePercent = Math.round((item.risk_score ?? 0) * 100);
                  const confidencePercent = Math.round((item.confidence_score ?? 0) * 100);

                  return (
                    <tr
                      key={item.case_id}
                      className="hover:bg-slate-50/60 dark:hover:bg-slate-700/20 transition-colors group"
                    >
                      {/* Case ID */}
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900 dark:text-slate-100 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span>{item.case_number}</span>
                          {item.priority === 'URGENT_P1' && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-rose-600 text-white animate-pulse">
                              P1
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Product */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-bold text-slate-900 dark:text-white truncate">
                          {item.product_name}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {item.brand ? <span className="text-slate-500 font-medium">{item.brand} • </span> : null}
                          {item.category?.replace(/_/g, ' ') || 'General Food'}
                        </div>
                      </td>

                      {/* Risk Score */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                scorePercent >= 70
                                  ? 'bg-red-500'
                                  : scorePercent >= 40
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(100, scorePercent)}%` }}
                            ></div>
                          </div>
                          <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                            {item.risk_score !== null && item.risk_score !== undefined
                              ? item.risk_score.toFixed(2)
                              : '—'}
                          </span>
                        </div>
                      </td>

                      {/* Risk Level */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide border ${riskStyle.bg} ${riskStyle.text} ${riskStyle.border}`}
                        >
                          {item.risk_level || 'LOW'}
                        </span>
                      </td>

                      {/* Confidence */}
                      <td className="py-3.5 px-4 whitespace-nowrap font-mono text-slate-600 dark:text-slate-300">
                        {item.confidence_score !== null && item.confidence_score !== undefined
                          ? `${confidencePercent}%`
                          : '—'}
                      </td>

                      {/* Submission Date */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-slate-500 dark:text-slate-400 text-[11px]">
                        {item.submitted_at || item.created_at
                          ? new Date(item.submitted_at || item.created_at).toLocaleDateString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                            })
                          : '—'}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${statusStyle.bg} ${statusStyle.text}`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`}></span>
                          {statusStyle.label}
                        </span>
                      </td>

                      {/* Authority Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Evidence Package Button */}
                          <Link
                            href={`/dashboard/cases/${item.case_id}/evidence`}
                            className="p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            title="Inspect Evidence Chain"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                          </Link>

                          {/* Open Dossier Button */}
                          <Link
                            href={`/dashboard/cases/${item.case_id}/analysis`}
                            className="p-1.5 rounded-lg text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
                            title="Open Deep Analysis Dossier"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                          </Link>

                          {/* Phase 15: Download PDF Report Button */}
                          <button
                            onClick={() => downloadCaseReportPdf(item.case_id, item.case_number)}
                            className="p-1.5 rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                            title="Download Certified Compliance Report (PDF)"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </button>

                          {/* Start Review (if PRIORITY_REVIEW or STANDARD_REVIEW) */}
                          {item.status === 'PRIORITY_REVIEW' || item.status === 'STANDARD_REVIEW' ? (
                            <button
                              onClick={() => handleStartReview(item)}
                              className="px-2 py-1 rounded-lg text-[11px] font-bold text-white bg-amber-600 hover:bg-amber-700 transition-colors"
                              title="Assign and start active review"
                            >
                              Start Review
                            </button>
                          ) : null}

                          {/* Record Authority Review Decision */}
                          <button
                            onClick={() => {
                              setActiveReviewCase(item);
                              setTargetStatus('UNDER_REVIEW');
                            }}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm"
                            title="Record statutory officer review and enforcement action"
                          >
                            Add Review
                          </button>

                          {/* Quick Status Update */}
                          <button
                            onClick={() => {
                              setActiveStatusCase(item);
                              setNewStatusValue(item.status);
                            }}
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            title="Update statutory status"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: Authority Review Action Modal */}
      {activeReviewCase && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-black uppercase tracking-widest text-emerald-600 dark:text-emerald-400">
                  Statutory Enforcement Action
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Authority Case Review: #{activeReviewCase.case_number}
                </h3>
                <p className="text-xs text-slate-500">{activeReviewCase.product_name}</p>
              </div>
              <button
                onClick={() => setActiveReviewCase(null)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleSubmitReview} className="p-6 space-y-4">
              {/* Action Selector */}
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Enforcement / Statutory Action
                </label>
                <select
                  value={reviewAction}
                  onChange={(e) => setReviewAction(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-medium"
                >
                  <option value="ISSUE_SECTION_32_NOTICE">Issue Statutory Improvement Notice (Sec 32, FSS Act)</option>
                  <option value="APPROVE_INSPECTION">Approve Field Inspection & Physical Sampling</option>
                  <option value="ORDER_LAB_TESTING">Refer Sample to NABL Accredited Food Lab</option>
                  <option value="SEIZE_PRODUCT">Order Seizure of Non-Compliant Consignments</option>
                  <option value="REQUEST_REANALYSIS">Request Additional Evidence / Re-extraction</option>
                  <option value="DISMISS_CASE">Dismiss Case (Unsubstantiated Allegation)</option>
                  <option value="CLOSE_NO_ACTION">Close Case - No Further Enforcement Action</option>
                </select>
              </div>

              {/* Target Status */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                    Transition Status To
                  </label>
                  <select
                    value={targetStatus}
                    onChange={(e) => setTargetStatus(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-medium"
                  >
                    <option value="UNDER_REVIEW">UNDER_REVIEW (Active Investigation)</option>
                    <option value="REVIEW_COMPLETED">REVIEW_COMPLETED (Action Rendered)</option>
                    <option value="RESOLVED">RESOLVED (Remediated)</option>
                    <option value="CLOSED">CLOSED (Docket Concluded)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                    Compliance Deadline (Days)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="90"
                    value={statutoryDays}
                    onChange={(e) => setStatutoryDays(parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                    placeholder="e.g. 14 days"
                  />
                </div>
              </div>

              {/* Review Notes */}
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Statutory Review Notes & Legal Findings <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={4}
                  required
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="State officer observations, referenced sections of FSS Act (e.g. Sec 24, 32, 53), lab testing instructions, or grounds for dismissal..."
                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 leading-relaxed"
                ></textarea>
              </div>

              {/* Audit Logging Notice */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-2">
                <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>
                  This decision will be cryptographically attributed to your Officer Badge ID in the immutable Audit Log.
                </span>
              </div>

              {/* Modal Buttons */}
              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setActiveReviewCase(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingReview}
                  className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm disabled:opacity-50"
                >
                  {isSubmittingReview ? 'Recording Action...' : 'Commit Sovereign Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Quick Status Update Modal */}
      {activeStatusCase && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                  Docket State Transition
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Update Case Status: #{activeStatusCase.case_number}
                </h3>
              </div>
              <button
                onClick={() => setActiveStatusCase(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-xl"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmitStatusUpdate} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                  New Status
                </label>
                <select
                  value={newStatusValue}
                  onChange={(e) => setNewStatusValue(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white font-semibold"
                >
                  <option value="PRIORITY_REVIEW">PRIORITY_REVIEW</option>
                  <option value="STANDARD_REVIEW">STANDARD_REVIEW</option>
                  <option value="UNDER_REVIEW">UNDER_REVIEW</option>
                  <option value="REVIEW_COMPLETED">REVIEW_COMPLETED</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Reason for Transition
                </label>
                <input
                  type="text"
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  placeholder="e.g. Officer desk reassignment, sample dispatched"
                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setActiveStatusCase(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingStatus}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 transition-colors disabled:opacity-50"
                >
                  {isSubmittingStatus ? 'Updating...' : 'Update Status'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
