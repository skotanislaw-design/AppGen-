import type { ExtraFinding, Priority, Severity, Suggestion } from '../types';

const PRIORITY_META: Record<Priority, { label: string; color: string; rank: number }> = {
  critical: { label: 'Κρίσιμη', color: '#f87171', rank: 0 },
  high: { label: 'Υψηλή', color: '#fb923c', rank: 1 },
  medium: { label: 'Μεσαία', color: '#C6A75E', rank: 2 },
  low: { label: 'Χαμηλή', color: '#9BA8B7', rank: 3 },
};

const SEVERITY_META: Record<Severity, { label: string; color: string }> = {
  critical: { label: 'Κρίσιμο', color: '#f87171' },
  major: { label: 'Σοβαρό', color: '#fb923c' },
  minor: { label: 'Ήσσον', color: '#9BA8B7' },
};

interface SuggestionsProps {
  suggestions: Suggestion[];
  extraFindings: ExtraFinding[];
}

export const Suggestions: React.FC<SuggestionsProps> = ({ suggestions, extraFindings }) => {
  const sorted = [...suggestions].sort(
    (a, b) => PRIORITY_META[a.priority].rank - PRIORITY_META[b.priority].rank,
  );

  return (
    <div className="flex flex-col gap-8">
      {extraFindings.length > 0 && (
        <div>
          <h3 className="mb-3 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
            Πρόσθετα ευρήματα
          </h3>
          <div className="flex flex-col gap-3">
            {extraFindings.map((f, i) => {
              const meta = SEVERITY_META[f.severity];
              return (
                <div key={i} className="glass-card p-5">
                  <div className="mb-2 flex items-center gap-2">
                    <span
                      className="rounded-full px-3 py-0.5 text-xs font-semibold"
                      style={{
                        color: meta.color,
                        background: `${meta.color}1f`,
                        border: `1px solid ${meta.color}55`,
                      }}
                    >
                      {meta.label}
                    </span>
                    <span className="text-sm font-semibold text-white/90">{f.title}</span>
                  </div>
                  <p className="text-sm leading-relaxed text-silver-light">{f.commentary}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-3 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
          Βελτιωτικές προτάσεις
        </h3>
        {sorted.length === 0 ? (
          <p className="text-sm text-silver">Δεν προτάθηκαν βελτιώσεις.</p>
        ) : (
          <ol className="flex flex-col gap-3">
            {sorted.map((s, i) => {
              const meta = PRIORITY_META[s.priority];
              return (
                <li key={i} className="glass-card p-5">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span
                      className="rounded-full px-3 py-0.5 text-xs font-semibold"
                      style={{
                        color: meta.color,
                        background: `${meta.color}1f`,
                        border: `1px solid ${meta.color}55`,
                      }}
                    >
                      Προτεραιότητα: {meta.label}
                    </span>
                    <span className="text-xs uppercase tracking-wider text-silver">{s.target}</span>
                  </div>
                  <p className="mb-2 text-sm leading-relaxed text-white/90">{s.proposed_action}</p>
                  <p className="text-xs leading-relaxed text-silver">{s.rationale}</p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
};
