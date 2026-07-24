// Nomos One — σελίδα module «Έλεγχος Δικογράφου».
//
// Ακολουθεί τις συμβάσεις του Nomos One: functional component, default export
// για σελίδα, RBAC στο route level (βλ. runbook). Επαναχρησιμοποιεί τα
// components του αυτόνομου UI (ReportView / ProgressPanel / DocumentInput /
// ExemplarLibrary) — αντιγράψτε τα από το standalone frontend όπως περιγράφει
// το README και προσαρμόστε τα relative imports παρακάτω.
//
// Προαιρετικό: περνώντας `matterId` (π.χ. από το route /matters/:id/audit), το
// αποτέλεσμα συνδέεται με την υπόθεση μέσω του on_result hook του backend.

import { useEffect, useState } from 'react';
import { analyzeStream, fetchDocumentTypes } from './auditApi';
// Αντιγράψτε αυτά τα components από το standalone frontend/src/components:
import { DocumentInput } from './components/DocumentInput';
import { ExemplarLibrary } from './components/ExemplarLibrary';
import { ProgressPanel } from './components/ProgressPanel';
import { ReportView } from './components/ReportView';
import type { AuditorInfo, AuditReport, DocumentClassification, DocumentTypeInfo } from './types';

interface DocumentAuditPageProps {
  matterId?: string;
}

type Phase =
  | { name: 'idle' }
  | {
      name: 'running';
      step: 'classifying' | 'auditing' | 'firm_review';
      classification: DocumentClassification | null;
      auditor: AuditorInfo | null;
    }
  | { name: 'done'; report: AuditReport }
  | { name: 'error'; message: string };

type View = 'audit' | 'exemplars';

export default function DocumentAuditPage({ matterId }: DocumentAuditPageProps) {
  const [view, setView] = useState<View>('audit');
  const [phase, setPhase] = useState<Phase>({ name: 'idle' });
  const [documentTypes, setDocumentTypes] = useState<DocumentTypeInfo[]>([]);

  useEffect(() => {
    fetchDocumentTypes()
      .then(setDocumentTypes)
      .catch(() => setDocumentTypes([]));
  }, []);

  const runAnalysis = async (
    text: string,
    context: string | null,
    docTypeHint: string | null,
  ) => {
    setPhase({ name: 'running', step: 'classifying', classification: null, auditor: null });
    try {
      let classification: DocumentClassification | null = null;
      let auditor: AuditorInfo | null = null;
      for await (const event of analyzeStream(text, context, docTypeHint, matterId)) {
        switch (event.stage) {
          case 'classified':
            classification = event.data;
            setPhase({ name: 'running', step: 'auditing', classification, auditor: null });
            break;
          case 'auditing':
            auditor = event.data.auditor;
            setPhase({ name: 'running', step: 'auditing', classification, auditor });
            break;
          case 'firm_review':
            setPhase({ name: 'running', step: 'firm_review', classification, auditor });
            break;
          case 'complete':
            setPhase({ name: 'done', report: event.data });
            return;
          case 'error':
            setPhase({ name: 'error', message: event.data.detail });
            return;
          default:
            break;
        }
      }
      setPhase((p) =>
        p.name === 'done'
          ? p
          : { name: 'error', message: 'Η σύνδεση διακόπηκε πριν την ολοκλήρωση της ανάλυσης.' },
      );
    } catch (err) {
      setPhase({
        name: 'error',
        message: err instanceof Error ? err.message : 'Απρόβλεπτο σφάλμα.',
      });
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-gold">Έλεγχος Δικογράφου</h1>
          {matterId && (
            <p className="text-xs text-silver">Συνδεδεμένο με την υπόθεση {matterId}</p>
          )}
        </div>
        <nav className="inline-flex rounded-lg border border-gold/25 bg-white/5 p-1">
          <button
            type="button"
            className={`rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-widest transition ${
              view === 'audit' ? 'bg-gold text-navy' : 'text-silver hover:text-white'
            }`}
            onClick={() => setView('audit')}
          >
            Έλεγχος
          </button>
          <button
            type="button"
            className={`rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-widest transition ${
              view === 'exemplars' ? 'bg-gold text-navy' : 'text-silver hover:text-white'
            }`}
            onClick={() => setView('exemplars')}
          >
            Υποδείγματα
          </button>
        </nav>
      </div>

      {view === 'exemplars' ? (
        <ExemplarLibrary />
      ) : phase.name === 'idle' ? (
        <DocumentInput documentTypes={documentTypes} disabled={false} onSubmit={runAnalysis} />
      ) : phase.name === 'running' ? (
        <ProgressPanel state={phase.step} classification={phase.classification} auditor={phase.auditor} />
      ) : phase.name === 'done' ? (
        <ReportView report={phase.report} onReset={() => setPhase({ name: 'idle' })} />
      ) : (
        <div className="glass-card flex flex-col items-center gap-4 p-8 text-center">
          <p className="text-sm text-red-300">{phase.message}</p>
          <button type="button" className="btn-ghost" onClick={() => setPhase({ name: 'idle' })}>
            Επιστροφή
          </button>
        </div>
      )}
    </div>
  );
}
