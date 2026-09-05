'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  CaseListItem,
  fetchRecentCases,
  downloadCaseReportPdf,
  openCaseReportHtml,
} from '@/services/api';

export default function ReportsPage() {
  const [recentCases, setRecentCases] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloadingCaseId, setDownloadingCaseId] = useState<string | null>(null);

  useEffect(() => {
    fetchRecentCases(15)
      .then((data) => setRecentCases(data))
      .catch(() => setRecentCases([]))
      .finally(() => setLoading(false));
  }, []);

  const handleDownloadPdf = async (caseItem: CaseListItem) => {
    setDownloadingCaseId(caseItem.case_id);
    try {
      await downloadCaseReportPdf(caseItem.case_id, caseItem.case_number);
    } catch (err: any) {
      alert(err?.message || 'Failed to download PDF report');
    } finally {
      setDownloadingCaseId(null);
    }
  };

  const handleOpenHtml = async (caseId: string) => {
    try {
      await openCaseReportHtml(caseId);
    } catch (err: any) {
      alert(err?.message || 'Failed to open HTML report');
    }
  };

  const statutoryRegisters = [
    {
      title: 'Section 32 Improvement Notice Register (Q3 2026)',
      type: 'Statutory Notice Log',
      cases: '14 Notices Issued',
      date: '01 Sep 2026',
      status: 'FILED_WITH_DO',
      sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    },
    {
      title: 'Curative Claim Violations Intelligence Dossier',
      type: 'Adulteration & Deception Audit',
      cases: '8 Products Flagged',
      date: '28 Aug 2026',
      status: 'PUBLISHED',
      sha256: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    },
    {
      title: 'Form VA Field Inspection & Sample Register (DL-CENTRAL)',
      type: 'Sampling Chain of Custody',
      cases: '22 Samples Drawn',
      date: '24 Aug 2026',
      status: 'VERIFIED',
      sha256: '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 mb-2">
          <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
          Report Generation & Statutory Records (Phase 15)
        </div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          Product Compliance Risk Intelligence Reports
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
          Generate, preview, and download certified 8-section regulatory dossiers formatted for Designated Officers, Food Safety Officers, and Appellate Tribunals under the FSS Act, 2006.
        </p>
      </div>

      {/* Mandatory Statutory AI Decision-Support Notice */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-amber-500/20 text-amber-700 dark:text-amber-400 shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="text-xs space-y-1">
            <div className="font-bold text-amber-900 dark:text-amber-100 flex items-center gap-2">
              <span>STATUTORY GOVERNANCE MANDATE</span>
            </div>
            <p className="text-amber-800/90 dark:text-amber-300/90 leading-relaxed">
              Every generated compliance report is an <strong>AI-assisted decision-support assessment</strong>. Final regulatory determinations, Section 32 Improvement Notices, sample seizures, and prosecutions require sovereign review and endorsement by an authorized Food Safety Officer or Designated Officer.
            </p>
          </div>
        </div>
      </div>

      {/* Live Case Dossier Generator Section */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>Active Case Dossier Generator</span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-300 font-bold">
                Live PDF & HTML
              </span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Select any registered product docket to generate its official evidence-backed intelligence report.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center text-xs text-slate-400">
            <div className="inline-block w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mb-2"></div>
            <p>Loading active surveillance dockets...</p>
          </div>
        ) : recentCases.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            <p>No active case dockets found in the registry.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="py-2.5 px-3">Case ID</th>
                  <th className="py-2.5 px-3">Product Name</th>
                  <th className="py-2.5 px-3">Risk Level</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Report Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60 text-xs">
                {recentCases.map((c) => {
                  const isBusy = downloadingCaseId === c.case_id;
                  return (
                    <tr key={c.case_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-3 font-mono font-bold text-slate-900 dark:text-slate-200">
                        {c.case_number}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-slate-900 dark:text-white truncate max-w-xs">
                          {c.product_name}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {c.brand} &bull; {c.category?.replace(/_/g, ' ')}
                        </div>
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            c.risk_level === 'HIGH' || c.risk_level === 'CRITICAL'
                              ? 'bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900'
                              : c.risk_level === 'MEDIUM'
                              ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900'
                              : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900'
                          }`}
                        >
                          {c.risk_level || 'LOW'}
                        </span>
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                        {c.status}
                      </td>
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleOpenHtml(c.case_id)}
                            className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors inline-flex items-center gap-1.5"
                            title="Preview Interactive HTML Report"
                          >
                            <svg className="w-3.5 h-3.5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            <span>HTML</span>
                          </button>

                          <button
                            onClick={() => handleDownloadPdf(c)}
                            disabled={isBusy}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm inline-flex items-center gap-1.5 disabled:opacity-50"
                            title="Download Certified PDF Report"
                          >
                            {isBusy ? (
                              <span className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            )}
                            <span>Download PDF</span>
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

      {/* Historical Certified Registers */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Quarterly Statutory Registers & Cryptographic Dossiers
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Cryptographically sealed periodic notice registers filed with the Designated Officer.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {statutoryRegisters.map((report) => (
            <div
              key={report.title}
              className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1 max-w-xl">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                    {report.type}
                  </span>
                  <span className="text-xs font-mono text-slate-400">&bull; {report.date}</span>
                </div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {report.title}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Scope: <span className="font-semibold text-slate-700 dark:text-slate-300">{report.cases}</span>
                </p>
                <p className="text-[11px] font-mono text-slate-400 truncate">
                  SHA-256: {report.sha256}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => alert(`Downloading Certified Archive for: ${report.title}`)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors inline-flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  <span>Download Archive</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
