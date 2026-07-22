import type { AuthenticityVerdict, FirmStandardReview, TellType } from '../types';

const VERDICT_META: Record<AuthenticityVerdict, { label: string; color: string }> = {
  human_register: { label: 'Φυσικός δικανικός λόγος', color: '#4ade80' },
  borderline: { label: 'Οριακό — ενδείξεις μη φυσικού λόγου', color: '#fb923c' },
  ai_marked: { label: 'Φέρει ίχνη AI — εκτός προτύπου', color: '#f87171' },
};

const TELL_LABELS: Record<TellType, string> = {
  structure: 'Δομή',
  phrasing: 'Φρασεολογία',
  rhythm: 'Ρυθμός',
  register: 'Ύφος',
  citation: 'Τεκμηρίωση',
  other: 'Λοιπά',
};

interface FirmStandardSectionProps {
  review: FirmStandardReview;
}

export const FirmStandardSection: React.FC<FirmStandardSectionProps> = ({ review }) => {
  const meta = VERDICT_META[review.authenticity_verdict];
  return (
    <div className="glass-card p-6 md:p-8">
      <h3 className="mb-1 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
        Πρότυπο Γραφείου — Δικανικός λόγος &amp; γνησιότητα
      </h3>
      <p className="mb-4 text-xs text-silver">
        Επιμελητής Δικανικού Λόγου — υποδειγματικό επίπεδο γραφής, μηδενική ανοχή σε ίχνη AI
      </p>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span
          className="rounded-full px-4 py-1 text-sm font-semibold"
          style={{
            color: meta.color,
            background: `${meta.color}1f`,
            border: `1px solid ${meta.color}55`,
          }}
        >
          {meta.label}
        </span>
        <span className="text-sm text-silver-light">
          Εγγύτητα στο υποδειγματικό πρότυπο:{' '}
          <span className="font-display text-lg text-gold-light">{review.register_score}/100</span>
        </span>
      </div>

      <div className="mb-6 flex flex-col gap-3 text-sm leading-7 text-white/90">
        {review.assessment
          .split(/\n{2,}/)
          .filter((p) => p.trim())
          .map((p, i) => (
            <p key={i}>{p.trim()}</p>
          ))}
      </div>

      {review.ai_tell_findings.length > 0 && (
        <div className="mb-6">
          <h4 className="mb-3 text-sm font-semibold uppercase tracking-widest text-gold">
            Εντοπισμένες ενδείξεις AI ({review.ai_tell_findings.length})
          </h4>
          <div className="flex flex-col gap-3">
            {review.ai_tell_findings.map((f, i) => (
              <div key={i} className="rounded-lg border border-red-400/30 bg-red-400/5 p-4">
                <span className="mb-2 inline-block rounded-full border border-red-400/50 bg-red-400/10 px-3 py-0.5 text-xs font-semibold text-red-300">
                  {TELL_LABELS[f.tell_type]}
                </span>
                <blockquote className="mb-2 border-l-2 border-red-400/40 pl-3 text-sm italic text-silver-light">
                  «{f.quote}»
                </blockquote>
                <p className="text-sm leading-relaxed text-silver-light">{f.explanation}</p>
                {f.rewrite && (
                  <div className="mt-3 rounded border border-emerald-400/30 bg-emerald-400/5 p-3">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-emerald-300">
                      Προτεινόμενη αναδιατύπωση
                    </p>
                    <p className="text-sm italic leading-relaxed text-white/90">{f.rewrite}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {review.exemplary_gaps.length > 0 && (
        <div>
          <h4 className="mb-3 text-sm font-semibold uppercase tracking-widest text-gold">
            Απόσταση από το υποδειγματικό επίπεδο
          </h4>
          <div className="flex flex-col gap-3">
            {review.exemplary_gaps.map((g, i) => (
              <div key={i} className="rounded-lg border border-gold/20 bg-white/5 p-4">
                <p className="mb-1 text-sm font-semibold text-gold-light">{g.aspect}</p>
                <p className="mb-2 text-sm leading-relaxed text-silver-light">{g.gap}</p>
                <p className="text-sm leading-relaxed text-white/85">{g.proposed_action}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
