interface ScoreBadgeProps {
  label: string
  score: number
  maxScore?: number
}

function tier(score: number, max: number): 'green' | 'yellow' | 'red' {
  const pct = (score / max) * 10   // normalise to 0–10 scale
  if (pct >= 8) return 'green'
  if (pct >= 5) return 'yellow'
  return 'red'
}

const TIER_CLASSES = {
  green:  'bg-green-50  text-green-700  ring-1 ring-green-200',
  yellow: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
  red:    'bg-red-50    text-red-700    ring-1 ring-red-200',
}

export default function ScoreBadge({ label, score, maxScore = 10 }: ScoreBadgeProps) {
  const t = tier(score, maxScore)
  return (
    <div className={`flex flex-col items-center rounded-lg px-3 py-2 ${TIER_CLASSES[t]}`}>
      <span className="text-lg font-bold tabular-nums leading-none">
        {Number.isInteger(score) ? score : score.toFixed(1)}
      </span>
      <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wide opacity-75">
        {label}
      </span>
    </div>
  )
}
