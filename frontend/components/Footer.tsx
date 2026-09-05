import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-500 dark:text-slate-400">
        <div className="flex flex-col gap-1 text-center md:text-left">
          <p className="font-semibold text-slate-700 dark:text-slate-300">
            DRISHTI &bull; Food Safety & Compliance Surveillance Platform
          </p>
          <p>
            Architected in compliance with Food Safety and Standards Act, 2006 (Sections 23, 24, 32, 38).
          </p>
        </div>

        <div className="flex items-center gap-6 font-mono text-[11px]">
          <span>FastAPI v0.110+</span>
          <span>&bull;</span>
          <span>Next.js 16 (App Router)</span>
          <span>&bull;</span>
          <span>PostgreSQL 16</span>
          <span>&bull;</span>
          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Phase 1 Foundation</span>
        </div>
      </div>
    </footer>
  );
};
