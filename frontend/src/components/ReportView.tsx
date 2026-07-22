import type { AuditReport } from '../types';
import { CategoryBreakdown } from './CategoryBreakdown';
import { CriteriaList } from './CriteriaList';
import { ScoreGauge } from './ScoreGauge';
import { Suggestions } from './Suggestions';

interface ReportViewProps {
  report: AuditReport;
  onReset: () => void;
}

export const ReportView: React.FC<ReportViewProps> = ({ report, onReset }) => (
  <div className="flex flex-col gap-8">
    <div className="glass-card flex flex-col items-center gap-8 p-6 md:flex-row md:items-start md:p-8">
      <ScoreGauge score={report.score.overall} verdict={report.score.verdict} />
      <div className="flex w-full flex-1 flex-col gap-5">
        <div>
          <p className="text-xs uppercase tracking-widest text-silver">Ταξινόμηση</p>
          <h2 className="font-display text-3xl font-semibold text-white">
            {report.classification.label}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-silver-light">
            {report.classification.summary}
          </p>
          {report.classification.court_or_authority && (
            <p className="mt-1 text-xs text-silver">
              Απευθύνεται: {report.classification.court_or_authority}
            </p>
          )}
        </div>
        <CategoryBreakdown categories={report.score.categories} />
        <p className="text-sm leading-relaxed text-silver-light">{report.score.verdict_detail}</p>
        {report.score.capped && report.score.cap_reason && (
          <p className="rounded-lg border border-red-400/40 bg-red-400/10 p-3 text-sm text-red-200">
            {report.score.cap_reason}
          </p>
        )}
      </div>
    </div>

    <div className="glass-card p-6 md:p-8">
      <h3 className="mb-3 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
        Συνολική αξιολόγηση
      </h3>
      <div className="flex flex-col gap-4 text-sm leading-7 text-white/90">
        {report.overall_assessment
          .split(/\n{2,}/)
          .filter((p) => p.trim())
          .map((p, i) => (
            <p key={i}>{p.trim()}</p>
          ))}
      </div>
    </div>

    <Suggestions suggestions={report.suggestions} extraFindings={report.extra_findings} />

    <CriteriaList criteria={report.criteria} />

    <div className="flex items-center justify-between">
      <p className="text-xs text-silver">
        Μοντέλο: {report.model} · Ο έλεγχος συνεπικουρεί, δεν υποκαθιστά, τη δικηγορική κρίση.
      </p>
      <button type="button" className="btn-ghost" onClick={onReset}>
        Νέος έλεγχος
      </button>
    </div>
  </div>
);
