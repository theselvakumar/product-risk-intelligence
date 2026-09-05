'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { UserProfile } from '@/types';

interface HeaderProps {
  user: UserProfile | null;
  onOpenSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ user, onOpenSidebar }) => {
  const pathname = usePathname();

  const getPageTitle = () => {
    if (pathname === '/dashboard') return 'Regulatory Intelligence Overview';
    if (pathname === '/dashboard/submit') return 'Submit Product for Surveillance';
    if (pathname === '/dashboard/cases') return 'Statutory Case Registry';
    if (pathname === '/dashboard/priority') return 'Priority Review & Critical Triage';
    if (pathname === '/dashboard/reports') return 'Statutory Compliance Reports & Notices';
    if (pathname === '/dashboard/profile') return 'Officer Profile & Security Credentials';
    return 'Authority Workspace';
  };

  return (
    <header className="sticky top-0 z-30 h-16 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 sm:px-8 flex items-center justify-between">
      {/* Left: Mobile Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenSidebar}
          className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800"
          aria-label="Toggle Navigation Drawer"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div>
          <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400">
            <span>DRISHTI</span>
            <span>/</span>
            <span className="text-slate-600 dark:text-slate-300">Workspace</span>
          </div>
          <h1 className="text-base font-black tracking-tight text-slate-900 dark:text-white">
            {getPageTitle()}
          </h1>
        </div>
      </div>

      {/* Right: Security Pill & Jurisdiction Badges */}
      <div className="flex items-center gap-3">
        {/* Jurisdiction Territory */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>{user?.jurisdiction_district || 'DL-CENTRAL'}, {user?.jurisdiction_state || 'DL'}</span>
        </div>

        {/* Cryptographic Session Pill */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-[11px] font-mono font-bold">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <span>HS256 Verified</span>
        </div>
      </div>
    </header>
  );
};
