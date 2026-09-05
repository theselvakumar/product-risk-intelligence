'use client';

import React, { useEffect, useState } from 'react';
import { fetchSystemHealth } from '@/services/api';
import { SystemHealth } from '@/types';

export const SystemStatusWidget: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastCheck, setLastCheck] = useState<string>('');

  const checkHealth = async () => {
    setLoading(true);
    const data = await fetchSystemHealth();
    setHealth(data);
    setLastCheck(new Date().toLocaleTimeString());
    setLoading(false);
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // 30s poll
    return () => clearInterval(interval);
  }, []);

  const isOnline = health?.status === 'ok';
  const dbConnected = health?.database?.status === 'connected';

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <span className={`w-3.5 h-3.5 rounded-full ${isOnline ? 'bg-emerald-500 ring-4 ring-emerald-500/20' : 'bg-amber-500 ring-4 ring-amber-500/20'}`} />
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white text-base">
              System Infrastructure Connectivity
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Live FastAPI Backend Diagnostics & Database Gateway
            </p>
          </div>
        </div>

        <button
          onClick={checkHealth}
          disabled={loading}
          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors disabled:opacity-50"
        >
          {loading ? 'Probing...' : 'Refresh Status'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Backend API Status */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            FastAPI Backend
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`font-bold text-sm ${isOnline ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
              {isOnline ? 'ONLINE (200 OK)' : 'DISCONNECTED'}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            GET /health
          </p>
        </div>

        {/* Database Status */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            PostgreSQL Gateway
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`font-bold text-sm ${dbConnected ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-600 dark:text-slate-400'}`}>
              {dbConnected ? 'CONNECTED' : 'CONFIGURED (STANDBY)'}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            {health?.database?.latency_ms ? `${health.database.latency_ms} ms` : 'Pool Ready'}
          </p>
        </div>

        {/* Deployment Environment */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Active Environment
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-bold text-sm text-slate-900 dark:text-white capitalize">
              {health?.environment || 'development'}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            v{health?.version || '0.1.0'}
          </p>
        </div>

        {/* Last Probe Time */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Last Telemetry Probe
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-sm font-semibold text-slate-800 dark:text-slate-200">
              {lastCheck || 'Checking...'}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
            Auto-polling every 30s
          </p>
        </div>
      </div>
    </div>
  );
};
