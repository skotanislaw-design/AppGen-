import { useEffect, useState } from 'react';
import { DocumentInput } from './components/DocumentInput';
import { ProgressPanel } from './components/ProgressPanel';
import { ReportView } from './components/ReportView';
import { analyzeStream, fetchDocumentTypes } from './lib/api';
import type {
  AuditorInfo,
  AuditReport,
  DocumentClassification,
  DocumentTypeInfo,
} from './types';

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

export default function App() {
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
      for await (const event of analyzeStream(text, context, docTypeHint)) {
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
      // Το stream έκλεισε χωρίς complete/error — διακοπή σύνδεσης.
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
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10 md:px-8">
      <header className="mb-10 text-center">
        <div className="mx-auto mb-4 h-0.5 w-16 bg-gradient-to-r from-gold via-gold-light to-gold-dark" />
        <p className="text-xs uppercase tracking-[0.3em] text-silver">
          Skotanis &amp; Associates · Elite Legal Advocacy
        </p>
        <h1 className="mt-2 font-display text-5xl font-light">
          <span className="gold-text-gradient">Nomos Audit</span>
        </h1>
        <p className="mt-2 text-sm text-silver-light">
          Αυστηρός έλεγχος νομικής πληρότητας δικογράφων — ποινικά, αστικά, διοικητικά, εξώδικα
        </p>
      </header>

      <main className="flex-1">
        {phase.name === 'idle' && (
          <DocumentInput documentTypes={documentTypes} disabled={false} onSubmit={runAnalysis} />
        )}
        {phase.name === 'running' && (
          <ProgressPanel
            state={phase.step}
            classification={phase.classification}
            auditor={phase.auditor}
          />
        )}
        {phase.name === 'done' && (
          <ReportView report={phase.report} onReset={() => setPhase({ name: 'idle' })} />
        )}
        {phase.name === 'error' && (
          <div className="glass-card flex flex-col items-center gap-4 p-8 text-center">
            <p className="text-sm text-red-300">{phase.message}</p>
            <button type="button" className="btn-ghost" onClick={() => setPhase({ name: 'idle' })}>
              Επιστροφή
            </button>
          </div>
        )}
      </main>

      <footer className="mt-12 border-t border-white/10 pt-6 text-center text-xs text-silver">
        <p>
          Μύκονος: Αεροδρόμιο Μυκόνου · +30 2289 100 111 &nbsp;|&nbsp; Αθήνα: Βαλαωρίτου 17,
          Κολωνάκι &nbsp;|&nbsp; skotanislaw.gr · ΑΜ ΔΣΣ 228
        </p>
      </footer>
    </div>
  );
}
