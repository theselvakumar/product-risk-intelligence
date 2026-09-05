'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchCurrentOfficer, getStoredToken } from '@/lib/auth';

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace('/login');
      return;
    }

    fetchCurrentOfficer().then((profile) => {
      if (profile) {
        router.replace('/dashboard');
      } else {
        router.replace('/login');
      }
    });
  }, [router]);

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center gap-4">
      <div className="w-10 h-10 rounded-full border-2 border-emerald-600 border-t-transparent animate-spin" />
      <div className="text-center">
        <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
          DRISHTI Regulatory Authority Portal
        </p>
        <p className="text-xs font-mono text-slate-500 tracking-wider uppercase mt-1">
          Verifying Clearance & Routing...
        </p>
      </div>
    </div>
  );
}
