'use client';

import React from 'react';
import { DashboardMetricsData } from '@/services/api';

interface MetricsGridProps {
  metrics: DashboardMetricsData | null;
  loading: boolean;
}

export const MetricsGrid: React.FC<MetricsGridProps> = ({ metrics, loading }) => {
  const cards = [
    {
      title: 'Total Cases',
      value: metrics?.total_cases ?? 6,
      subtext: 'Active territorial docket',
      accent: 'border-slate-300 dark:border-slate-700',
      badge: 'Surveillance',
      badgeColor: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
      icon: (
        <svg className="w-5 h-5 text-slate-600 dark:text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
    },
    {
      title: 'Cases Under Analysis',
      value: metrics?.cases_under_analysis ?? 2,
      subtext: 'Triaging & cross-source audit',
      accent: 'border-blue-500/40',
      badge: 'In Progress',
      badgeColor: 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800',
      icon: (
        <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      ),
    },
    {
      title: 'Low Risk',
      value: metrics?.low_risk ?? 1,
      subtext: 'Compliant & resolved samples',
      accent: 'border-emerald-500/40',
      badge: 'Compliant',
      badgeColor: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800',
      icon: (
        <svg className="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title: 'Medium Risk',
      value: metrics?.medium_risk ?? 2,
      subtext: 'Minor labelling discrepancies',
      accent: 'border-amber-500/40',
      badge: 'Advisory',
      badgeColor: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800',
      icon: (
        <svg className="w-5 h-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
    {
      title: 'High Risk',
      value: metrics?.high_risk ?? 3,
      subtext: 'Curative claims / toxicity risk',
      accent: 'border-red-500/50',
      badge: 'Action Required',
      badgeColor: 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800 animate-pulse',
      icon: (
        <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title: 'Pending Review',
      value: metrics?.pending_review ?? 3,
      subtext: 'Awaiting Section 32 orders',
      accent: 'border-purple-500/40',
      badge: 'Designated Officer',
      badgeColor: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800',
      icon: (
        <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className={`p-4 rounded-2xl bg-white dark:bg-slate-900 border ${card.accent} shadow-sm transition-all hover:shadow-md flex flex-col justify-between`}
        >
          <div className="flex items-center justify-between gap-2 mb-3">
            <span className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800">
              {card.icon}
            </span>
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${card.badgeColor}`}>
              {card.badge}
            </span>
          </div>

          <div>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              {card.title}
            </p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 dark:text-white font-mono">
                {loading ? '...' : card.value}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500 truncate">
              {card.subtext}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};
