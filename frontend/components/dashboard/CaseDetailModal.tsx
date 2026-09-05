'use client';

import React from 'react';
import { CaseListItem } from '@/services/api';

interface CaseDetailModalProps {
  caseItem: CaseListItem | null;
  onClose: () => void;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({ caseItem, onClose }) => {
  if (!caseItem) return null;

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
        return 'bg-red-100 dark:bg-red-950/80 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800';
      case 'HIGH':
        return 'bg-orange-100 dark:bg-orange-950/80 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800';
      case 'MEDIUM':
        return 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800';
      default:
        return 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">
                {caseItem.case_number}
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border font-mono ${getRiskBadge(caseItem.risk_level)}`}>
                {caseItem.risk_level} (Risk Score: {caseItem.risk_score.toFixed(1)})
              </span>
            </div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
              {caseItem.product_name}
            </h3>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {/* Statutory Title & Description */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
            <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
              Statutory Surveillance Finding
            </p>
            <p className="text-sm font-semibold text-slate-900 dark:text-white leading-relaxed">
              {caseItem.title}
            </p>
          </div>

          {/* Product & Case Metadata */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Brand / Manufacturer</span>
              <span className="font-bold text-slate-900 dark:text-white">{caseItem.brand}</span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Regulatory Category</span>
              <span className="font-bold text-slate-900 dark:text-white truncate block">{caseItem.category}</span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Docket Submission</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">
                {new Date(caseItem.submission_date).toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Enforcement Status</span>
              <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                {caseItem.status}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Triage Priority</span>
              <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                {caseItem.priority}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800">
              <span className="text-slate-400 block font-semibold">Jurisdiction</span>
              <span className="font-bold text-slate-800 dark:text-slate-200">
                DL-CENTRAL (Delhi)
              </span>
            </div>
          </div>

          {/* Legal references notice */}
          <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 text-xs text-amber-800 dark:text-amber-300">
            <span className="font-bold">Applicable Act: </span>
            Food Safety & Standards Act, 2006 (Section 23 Packaging & Labelling, Section 24 Prohibition of Misleading Claims, Section 32 Improvement Notices).
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 dark:bg-slate-950/80 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            Close Docket
          </button>
          <button
            onClick={() => {
              alert(`Form VA Sampling Notice prepared for ${caseItem.case_number}. (Phase 5 Feature)`);
              onClose();
            }}
            className="px-4 py-2 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-colors"
          >
            Issue Form VA Sampling Order &rarr;
          </button>
        </div>
      </div>
    </div>
  );
};
