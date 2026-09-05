import React from 'react';

interface MetricItem {
  title: string;
  value: string;
  subtext: string;
  badge: string;
  accent: string;
}

export const StatCards: React.FC = () => {
  const metrics: MetricItem[] = [
    {
      title: 'Target Regulatory Domains',
      value: '6 Regulations',
      subtext: 'FSS Act 2006, Labelling 2020, Claims 2018, Additives 2011, RDA 2022',
      badge: 'Statutory Core',
      accent: 'border-l-emerald-500',
    },
    {
      title: 'Planned Ingestion Channels',
      value: '4 Modalities',
      subtext: 'Product URLs, FOP/BOP Packaging, Warehouse Scans, Catalog Text',
      badge: 'Multi-Modal',
      accent: 'border-l-teal-500',
    },
    {
      title: 'Dual-Verification Reasoning',
      value: 'Deterministic + RAG',
      subtext: 'Zero-hallucination guardrails with mathematical threshold audits',
      badge: 'Neuro-Symbolic',
      accent: 'border-l-indigo-500',
    },
    {
      title: 'Evidence Dossier Output',
      value: 'PDF/A + SHA-256',
      subtext: 'Legally defensible audit records with visual bounding-box evidence',
      badge: 'Section 32/38',
      accent: 'border-l-purple-500',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((item, index) => (
        <div
          key={index}
          className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm border-l-4 ${item.accent} flex flex-col justify-between`}
        >
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                {item.title}
              </span>
              <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                {item.badge}
              </span>
            </div>
            <div className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              {item.value}
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            {item.subtext}
          </p>
        </div>
      ))}
    </div>
  );
};
