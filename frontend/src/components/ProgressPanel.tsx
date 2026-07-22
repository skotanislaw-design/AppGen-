import type { AuditorInfo, DocumentClassification } from '../types';

export type ProgressState = 'classifying' | 'auditing';

interface ProgressPanelProps {
  state: ProgressState;
  classification: DocumentClassification | null;
  auditor: AuditorInfo | null;
}

const Spinner = () => (
  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gold border-t-transparent" />
);

const Check = () => <span className="text-emerald-400">✓</span>;

export const ProgressPanel: React.FC<ProgressPanelProps> = ({
  state,
  classification,
  auditor,
}) => (
  <div className="glass-card flex flex-col gap-4 p-6 md:p-8">
    <div className="flex items-center gap-3 text-sm">
      {state === 'classifying' ? <Spinner /> : <Check />}
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
      {state === 'auditing' ? <Spinner /> : <span className="w-4 text-silver">·</span>}
      <span className={state === 'auditing' ? 'text-white' : 'text-silver'}>
        Έλεγχος πληρότητας από ειδικό του κλάδου — κριτήριο προς κριτήριο
      </span>
    </div>
    {state === 'auditing' && auditor && (
      <div className="ml-7 rounded-lg border border-gold/20 bg-white/5 p-4 text-sm">
        <p className="font-semibold text-gold-light">Ανατέθηκε σε: {auditor.title}</p>
        <p className="mt-1 leading-relaxed text-silver-light">{auditor.description}</p>
      </div>
    )}
    {state === 'auditing' && (
      <p className="ml-7 text-xs leading-relaxed text-silver">
        Ο ενδελεχής έλεγχος διαρκεί συνήθως 1–3 λεπτά, αναλόγως της έκτασης του δικογράφου.
      </p>
    )}
  </div>
);
