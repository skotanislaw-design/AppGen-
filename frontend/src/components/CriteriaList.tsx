import { useMemo } from 'react';
import type { CriterionReport, CriterionStatus } from '../types';

const STATUS_META: Record<CriterionStatus, { label: string; color: string }> = {
  met: { label: 'Πλήρες', color: '#4ade80' },
  partially_met: { label: 'Μερικώς', color: '#fb923c' },
  missing: { label: 'Ελλείπει', color: '#f87171' },
  not_applicable: { label: 'Δεν εφαρμόζεται', color: '#9BA8B7' },
};

interface CriteriaListProps {
  criteria: CriterionReport[];
}

export const CriteriaList: React.FC<CriteriaListProps> = ({ criteria }) => {
  const grouped = useMemo(() => {
    const map = new Map<string, CriterionReport[]>();
    for (const c of criteria) {
      const list = map.get(c.category_label) ?? [];
      list.push(c);
      map.set(c.category_label, list);
    }
    return [...map.entries()];
  }, [criteria]);

  return (
    <div className="flex flex-col gap-8">
      {grouped.map(([label, items]) => (
        <div key={label}>
          <h3 className="mb-3 border-b border-gold/20 pb-2 font-display text-2xl font-semibold text-gold">
            {label}
          </h3>
          <div className="flex flex-col gap-3">
            {items.map((c) => {
              const meta = STATUS_META[c.status];
              return (
                <div key={c.criterion_id} className="glass-card p-5">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
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
                      {c.critical && (
                        <span className="rounded-full border border-red-400/50 bg-red-400/10 px-3 py-0.5 text-xs font-semibold text-red-300">
                          Κρίσιμο
                        </span>
                      )}
                    </div>
                    {c.status !== 'not_applicable' && (
                      <span className="font-display text-lg text-gold-light">{c.score}/100</span>
                    )}
                  </div>
                  <p className="mb-2 text-sm text-white/85">{c.text}</p>
                  <p className="text-sm leading-relaxed text-silver-light">{c.commentary}</p>
                  {c.evidence && (
                    <blockquote className="mt-3 border-l-2 border-gold/40 pl-3 text-sm italic text-silver">
                      «{c.evidence}»
                    </blockquote>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
