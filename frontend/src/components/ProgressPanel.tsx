import type { AuditorInfo, DocumentClassification } from '../types';

export type ProgressState = 'classifying' | 'auditing' | 'firm_review';

interface ProgressPanelProps {
  state: ProgressState;
  classification: DocumentClassification | null;
  auditor: AuditorInfo | null;
}

const Spinner = () => (
  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gold border-t-transparent" />
);

const Check = () => <span className="text-emerald-400">✓</span>;
const Dot = () => <span className="w-4 text-center text-silver">·</span>;

const ORDER: ProgressState[] = ['classifying', 'auditing', 'firm_review'];

const StepIcon: React.FC<{ step: ProgressState; current: ProgressState }> = ({
  step,
  current,
}) => {
  const stepIdx = ORDER.indexOf(step);
  const currentIdx = ORDER.indexOf(current);
  if (stepIdx < currentIdx) return <Check />;
  if (stepIdx === currentIdx) return <Spinner />;
  return <Dot />;
};

export const ProgressPanel: React.FC<ProgressPanelProps> = ({
  state,
  classification,
  auditor,
}) => (
  <div className="glass-card flex flex-col gap-4 p-6 md:p-8">
    <div className="flex items-center gap-3 text-sm">
      <StepIcon step="classifying" current={state} />
      <span className={state === 'classifying' ? 'text-white' : 'text-silver'}>
        Ταξινόμηση εγγράφου — είδος, κλάδος, δικονομικό πλαίσιο
      </span>
    </div>
    {classification && (
      <div className="ml-7 rounded-lg border border-gold/20 bg-white/5 p-4 text-sm">
        <p className="font-semibold text-gold-light">{classification.label}</p>
        <p className="mt-1 leading-relaxed text-silver-light">{classification.summary}</p>
      </div>
    )}

    <div className="flex items-center gap-3 text-sm">
      <StepIcon step="auditing" current={state} />
      <span className={state === 'auditing' ? 'text-white' : 'text-silver'}>
        Έλεγχος πληρότητας από ειδικό του κλάδου — κριτήριο προς κριτήριο
      </span>
    </div>
    {auditor && (
      <div className="ml-7 rounded-lg border border-gold/20 bg-white/5 p-4 text-sm">
        <p className="font-semibold text-gold-light">Ανατέθηκε σε: {auditor.title}</p>
        <p className="mt-1 leading-relaxed text-silver-light">{auditor.description}</p>
      </div>
    )}

    <div className="flex items-center gap-3 text-sm">
      <StepIcon step="firm_review" current={state} />
      <span className={state === 'firm_review' ? 'text-white' : 'text-silver'}>
        Πρότυπο γραφείου — υποδειγματικός δικανικός λόγος, ανίχνευση ιχνών AI
      </span>
    </div>

    <p className="text-xs leading-relaxed text-silver">
      Ο πλήρης έλεγχος διαρκεί συνήθως 2–4 λεπτά, αναλόγως της έκτασης του δικογράφου.
    </p>
  </div>
);
