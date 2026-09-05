'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchCurrentOfficer, getStoredToken } from '@/lib/auth';
import { UserProfile } from '@/types';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { Header } from '@/components/dashboard/Header';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace('/login');
      return;
    }

    fetchCurrentOfficer().then((profile) => {
      if (!profile) {
        router.replace('/login');
      } else {
        setUser(profile);
        setLoading(false);
      }
    });
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-emerald-600 border-t-transparent animate-spin"></div>
        <p className="text-xs font-mono text-slate-500 tracking-wider uppercase">
          Verifying Authority Clearance...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex">
      {/* Sidebar Navigation */}
      <Sidebar
        user={user}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Authority Workspace */}
      <div className="flex-1 flex flex-col lg:pl-72 min-w-0">
        {/* Dashboard Header */}
        <Header
          user={user}
          onOpenSidebar={() => setIsSidebarOpen(true)}
        />

        {/* Dynamic Content Area */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto space-y-8">
          {children}
        </main>
      </div>
    </div>
  );
}
