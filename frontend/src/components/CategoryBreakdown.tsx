import type { CategoryScore } from '../types';

interface CategoryBreakdownProps {
  categories: CategoryScore[];
}

function barColor(score: number): string {
  if (score >= 75) return '#4ade80';
  if (score >= 60) return '#C6A75E';
  if (score >= 40) return '#fb923c';
  return '#f87171';
}

export const CategoryBreakdown: React.FC<CategoryBreakdownProps> = ({ categories }) => (
  <div className="flex w-full flex-col gap-4">
    {categories.map((cat) => (
      <div key={cat.category}>
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-sm font-medium text-white/85">
            {cat.label}
            <span className="ml-2 text-xs text-silver">βάρος {(cat.weight * 100).toFixed(0)}%</span>
          </span>
          <span className="font-display text-xl text-gold-light">
            {cat.score === null ? '—' : `${cat.score.toFixed(0)}%`}
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
          {cat.score !== null && (
            <div
              className="h-full rounded-full"
              style={{
                width: `${cat.score}%`,
                background: barColor(cat.score),
                transition: 'width 0.8s ease',
              }}
            />
          )}
        </div>
      </div>
    ))}
  </div>
);
