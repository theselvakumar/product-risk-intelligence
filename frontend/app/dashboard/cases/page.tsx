'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { RecentCasesTable } from '@/components/dashboard/RecentCasesTable';
import { CaseListItem, fetchRecentCases } from '@/services/api';

export default function CasesRegistryPage() {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadCases = async () => {
    setLoading(true);
    try {
      const data = await fetchRecentCases(30);
      setCases(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black tracking-tight text-slate-900 dark:text-white">
            Statutory Case Registry
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Active and resolved product investigation dockets in Central Territorial Jurisdiction (DL-CENTRAL).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/submit"
            className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-colors inline-flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Register New Case</span>
          </Link>
        </div>
      </div>

      <RecentCasesTable
        cases={cases}
        loading={loading}
        onRefresh={loadCases}
      />
    </div>
  );
}
