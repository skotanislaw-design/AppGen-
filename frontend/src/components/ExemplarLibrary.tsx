import { useEffect, useMemo, useState } from 'react';
import { downloadExemplarDocx, fetchExemplar, fetchExemplars } from '../lib/api';
import type { ExemplarDetail, ExemplarSummary } from '../types';

const BRANCH_LABELS: Record<string, string> = {
  penal: 'Ποινικά',
  civil: 'Αστικά',
  administrative: 'Διοικητικά',
  extrajudicial: 'Εξώδικα',
  generic: 'Λοιπά',
};

const BRANCH_ORDER = ['penal', 'civil', 'administrative', 'extrajudicial', 'generic'];

export const ExemplarLibrary: React.FC = () => {
  const [summaries, setSummaries] = useState<ExemplarSummary[]>([]);
  const [selected, setSelected] = useState<ExemplarDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    fetchExemplars()
      .then(setSummaries)
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Αποτυχία φόρτωσης υποδειγμάτων.'),
      );
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, ExemplarSummary[]>();
    for (const s of summaries) {
      const list = map.get(s.branch) ?? [];
      list.push(s);
      map.set(s.branch, list);
    }
    return BRANCH_ORDER.filter((b) => map.has(b)).map(
      (b) => [b, map.get(b) as ExemplarSummary[]] as const,
    );
  }, [summaries]);

  const openExemplar = async (docType: string) => {
    setLoading(true);
    setError(null);
    try {
      setSelected(await fetchExemplar(docType));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Αποτυχία φόρτωσης υποδείγματος.');
    } finally {
      setLoading(false);
    }
  };

  const copyBody = async () => {
    if (!selected) return;
    await navigator.clipboard.writeText(selected.body);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const downloadDocx = async () => {
    if (!selected) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadExemplarDocx(selected.doc_type);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Αποτυχία λήψης DOCX.');
    } finally {
      setDownloading(false);
    }
  };

  if (selected) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button type="button" className="btn-ghost" onClick={() => setSelected(null)}>
            ← Βιβλιοθήκη
          </button>
          <div className="flex gap-3">
            <button type="button" className="btn-ghost" onClick={() => void copyBody()}>
              {copied ? 'Αντιγράφηκε ✓' : 'Αντιγραφή'}
            </button>
            <button
              type="button"
              className="btn-gold"
              disabled={downloading}
              onClick={() => void downloadDocx()}
            >
              {downloading ? 'Δημιουργία…' : 'Λήψη DOCX (επιστολόχαρτο)'}
            </button>
          </div>
        </div>
        {error && <p className="text-center text-sm text-red-300">{error}</p>}

        <div className="glass-card p-6 md:p-8">
          <p className="text-xs uppercase tracking-widest text-silver">
            {BRANCH_LABELS[selected.branch] ?? selected.branch} · {selected.doc_type_label}
          </p>
          <h2 className="mt-1 font-display text-3xl font-semibold text-gold">{selected.title}</h2>
          <p className="mt-2 text-sm leading-relaxed text-silver-light">{selected.scenario}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {selected.key_provisions.map((p, i) => (
              <span
                key={i}
                className="rounded-full border border-gold/30 bg-gold/10 px-3 py-0.5 text-xs text-gold-light"
              >
                {p}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gold/25 bg-[#f7f3ea] p-6 shadow-2xl md:p-10">
          <pre className="whitespace-pre-wrap font-display text-[15px] leading-7 text-[#1c2433]">
            {selected.body}
          </pre>
        </div>

        <div className="glass-card p-6 md:p-8">
          <h3 className="mb-4 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
            Σημειώσεις συντάξεως — η οικονομία του δικογράφου
          </h3>
          <div className="flex flex-col gap-4">
            {selected.drafting_notes.map((note, i) => (
              <div key={i} className="flex gap-3">
                <span className="mt-0.5 font-display text-xl text-gold">{i + 1}.</span>
                <p className="text-sm leading-relaxed text-silver-light">{note}</p>
              </div>
            ))}
          </div>
          <p className="mt-6 rounded-lg border border-gold/20 bg-white/5 p-4 text-xs leading-relaxed text-silver">
            Τα σημεία [ΣΥΜΠΛΗΡΩΣΤΕ] εξατομικεύονται ανά υπόθεση. Η νομολογία δεν
            συμπληρώνεται ποτέ χωρίς επαλήθευση σε τρέχουσα πηγή — το υπόδειγμα
            σημειώνει τη θέση της, όχι τον αριθμό της.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <p className="text-center text-sm leading-relaxed text-silver-light">
        Πλήρη σχέδια δικογράφων κατά το πρότυπο του γραφείου — νομική, ουσιαστική και
        δομική οικονομία — προς χρήση από τους συνεργάτες ως μέτρο του άρτιου.
      </p>
      {error && <p className="text-center text-sm text-red-300">{error}</p>}
      {loading && <p className="text-center text-sm text-silver">Φόρτωση…</p>}
      {grouped.map(([branch, items]) => (
        <div key={branch}>
          <h3 className="mb-3 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
            {BRANCH_LABELS[branch] ?? branch}
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {items.map((s) => (
              <button
                key={s.doc_type}
                type="button"
                className="glass-card p-5 text-left transition hover:border-gold/40"
                onClick={() => void openExemplar(s.doc_type)}
              >
                <p className="text-xs uppercase tracking-widest text-silver">{s.doc_type_label}</p>
                <p className="mt-1 font-display text-xl font-semibold text-gold-light">{s.title}</p>
                <p className="mt-2 text-sm leading-relaxed text-silver-light">{s.scenario}</p>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
