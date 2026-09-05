'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchCurrentOfficer, getStoredUser, logoutOfficer } from '@/lib/auth';
import { UserProfile } from '@/types';

export default function OfficerProfilePage() {
  const router = useRouter();
  const [officer, setOfficer] = useState<UserProfile | null>(null);

  useEffect(() => {
    fetchCurrentOfficer().then((u) => {
      setOfficer(u || getStoredUser());
    });
  }, []);

  const handleLogout = async () => {
    await logoutOfficer();
    router.push('/login');
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-black tracking-tight text-slate-900 dark:text-white">
          Officer Identity & Statutory Credentials
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Cryptographically verified authority credentials and enforcement territorial assignments under FSSAI.
        </p>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm space-y-6">
        {/* Officer Card Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 via-teal-600 to-indigo-600 flex items-center justify-center text-white font-extrabold text-2xl shadow-md">
              {officer?.full_name?.charAt(0) || 'O'}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                {officer?.full_name || 'Rajesh Sharma'}
              </h3>
              <p className="text-xs font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                Badge: {officer?.badge_id || 'FSO-DL-CENTRAL-012'}
              </p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="px-4 py-2 rounded-xl text-xs font-bold text-red-600 bg-red-50 dark:bg-red-950/50 hover:bg-red-100 dark:hover:bg-red-900/50 border border-red-200 dark:border-red-800 transition-colors"
          >
            Terminate Session & Sign Out
          </button>
        </div>

        {/* Credentials Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 font-semibold block uppercase tracking-wider text-[10px]">
              Statutory Role
            </span>
            <span className="mt-1 text-sm font-bold text-slate-900 dark:text-white font-mono">
              {officer?.role || 'AUTHORITY_OFFICER'}
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 font-semibold block uppercase tracking-wider text-[10px]">
              Official Email
            </span>
            <span className="mt-1 text-sm font-bold text-slate-900 dark:text-white font-mono">
              {officer?.email || 'officer@drishti.gov.in'}
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 font-semibold block uppercase tracking-wider text-[10px]">
              Assigned District
            </span>
            <span className="mt-1 text-sm font-bold text-slate-900 dark:text-white font-mono">
              {officer?.jurisdiction_district || 'DL-CENTRAL (Central Delhi)'}
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 font-semibold block uppercase tracking-wider text-[10px]">
              State Jurisdiction
            </span>
            <span className="mt-1 text-sm font-bold text-slate-900 dark:text-white font-mono">
              {officer?.jurisdiction_state || 'Delhi (National Capital)'}
            </span>
          </div>
        </div>

        {/* Security Session Advisory */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-2">
          <p className="font-bold text-slate-800 dark:text-slate-200">
            Security & Audit Trail Policy
          </p>
          <p className="leading-relaxed text-[11px]">
            This session is cryptographically bound to your official government IP and bearer token. Under FSS Act 2006 and IT Act 2000, all case inspections, field sampling orders, and statutory improvement notices issued under this session are permanently stored in immutable regulatory audit logs.
          </p>
        </div>
      </div>
    </div>
  );
}
