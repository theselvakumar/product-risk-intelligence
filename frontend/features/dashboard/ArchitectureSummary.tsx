import React from 'react';

export const ArchitectureSummary: React.FC = () => {
  const architecturalModules = [
    {
      title: 'Docs: Project Overview',
      file: 'docs/PROJECT_OVERVIEW.md',
      desc: 'Regulatory scope, user personas (FSO, DO, Analyst), and statutory mandates.',
      status: 'Ready (Phase 0)',
    },
    {
      title: 'Docs: System Architecture',
      file: 'docs/SYSTEM_ARCHITECTURE.md',
      desc: 'Modular monolith, Clean Architecture, async queues, and database entities.',
      status: 'Ready (Phase 0)',
    },
    {
      title: 'Docs: Data Flow & DTOs',
      file: 'docs/DATA_FLOW.md',
      desc: 'Sequence flows, canonical schemas, case lifecycle state machine.',
      status: 'Ready (Phase 0)',
    },
    {
      title: 'Docs: API Architecture',
      file: 'docs/API_ARCHITECTURE.md',
      desc: 'RESTful endpoints, SSE progress streaming, and RFC 7807 error format.',
      status: 'Ready (Phase 0)',
    },
    {
      title: 'Docs: AI Pipeline Design',
      file: 'docs/AI_PIPELINE.md',
      desc: 'Vision preprocessing, YOLOv8 zone layout, PaddleOCR, and Risk Scoring.',
      status: 'Ready (Phase 0)',
    },
    {
      title: 'Docs: Development Roadmap',
      file: 'docs/DEVELOPMENT_ROADMAP.md',
      desc: 'Phase 0 through 5 delivery milestones, acceptance criteria, and risk matrix.',
      status: 'Ready (Phase 0)',
    },
  ];

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 mb-6 gap-2">
        <div>
          <h3 className="font-bold text-slate-900 dark:text-white text-base">
            Phase 0 Technical Architecture Specifications
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Validated system blueprints guiding the DRISHTI implementation pipeline
          </p>
        </div>
        <span className="text-xs font-mono px-2.5 py-1 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 self-start sm:self-auto">
          All 7 Blueprint Docs Generated
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {architecturalModules.map((mod, idx) => (
          <div
            key={idx}
            className="p-4 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-200/80 dark:border-slate-800 flex flex-col justify-between hover:border-emerald-500/50 transition-colors"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
                  {mod.title}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-400">
                  {mod.status}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-3">
                {mod.desc}
              </p>
            </div>
            <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
              {mod.file}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
