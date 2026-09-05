'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { MetricsGrid } from '@/components/dashboard/MetricsGrid';
import { RecentCasesTable } from '@/components/dashboard/RecentCasesTable';
import {
  CaseListItem,
  DashboardMetricsData,
  fetchDashboardMetrics,
  fetchRecentCases,
} from '@/services/api';

export default function DashboardOverviewPage() {
  const [metrics, setMetrics] = useState<DashboardMetricsData | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [m, c] = await Promise.all([
        fetchDashboardMetrics(),
        fetchRecentCases(10),
      ]);
      setMetrics(m);
      setCases(c);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome & Surveillance Briefing Banner */}
      <div className="p-6 sm:p-8 rounded-3xl bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 text-white shadow-lg relative overflow-hidden">
        {/* Subtle geometric backdrop */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-radial from-emerald-500/10 to-transparent pointer-events-none"></div>

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold mb-3">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              CENTRAL SURVEILLANCE DESK ACTIVE
            </div>
            <h2 className="text-2xl sm:text-3xl font-black tracking-tight">
              Regulatory Intelligence & Enforcement Cockpit
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-slate-300 leading-relaxed">
              Real-time monitoring of food product claims, labelling non-compliances, and unauthorized health representations under FSS Act, 2006.
            </p>
          </div>

          {/* Primary Quick Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Link
              href="/dashboard/submit"
              className="px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 transition-all inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>Submit Product</span>
            </Link>

            <Link
              href="/dashboard/priority"
              className="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Priority Triage</span>
            </Link>
          </div>
        </div>
      </div>

      {/* 6 Required Dashboard Metrics */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Docket Health & Risk Distribution
          </h3>
          <span className="text-[11px] font-mono text-slate-400">
            Updated just now
          </span>
        </div>
        <MetricsGrid metrics={metrics} loading={loading} />
      </section>

      {/* Recent Regulatory Cases Table */}
      <section>
        <RecentCasesTable
          cases={cases}
          loading={loading}
          onRefresh={loadData}
        />
      </section>
    </div>
  );
}
