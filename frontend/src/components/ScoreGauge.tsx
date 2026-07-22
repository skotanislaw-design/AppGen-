interface ScoreGaugeProps {
  score: number;
  verdict: string;
}

function scoreColor(score: number): string {
  if (score >= 75) return '#4ade80';
  if (score >= 60) return '#C6A75E';
  if (score >= 40) return '#fb923c';
  return '#f87171';
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({ score, verdict }) => {
  const radius = 84;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative h-52 w-52">
        <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90">
          <circle
            cx="100"
            cy="100"
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="12"
          />
          <circle
            cx="100"
            cy="100"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference - filled}`}
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-6xl font-light" style={{ color }}>
            {score.toFixed(0)}
          </span>
          <span className="text-xs uppercase tracking-widest text-silver">επί τοις 100</span>
        </div>
      </div>
      <span
        className="rounded-full px-4 py-1 text-sm font-semibold"
        style={{ color, background: `${color}22`, border: `1px solid ${color}55` }}
      >
        {verdict}
      </span>
    </div>
  );
};
