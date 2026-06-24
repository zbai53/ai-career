interface ScoreCardProps {
  label: string
  score: number
  maxScore?: number
}

function scoreClasses(pct: number): { bar: string; text: string; bg: string } {
  if (pct >= 70) return { bar: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50' }
  if (pct >= 50) return { bar: 'bg-yellow-500', text: 'text-yellow-700', bg: 'bg-yellow-50' }
  return { bar: 'bg-red-500', text: 'text-red-700', bg: 'bg-red-50' }
}

export default function ScoreCard({ label, score, maxScore = 100 }: ScoreCardProps) {
  const pct = Math.min(100, Math.max(0, (score / maxScore) * 100))
  const { bar, text, bg } = scoreClasses(pct)

  return (
    <div className={`rounded-xl p-4 ${bg} space-y-2`}>
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-gray-600">{label}</span>
        <span className={`text-lg font-bold tabular-nums ${text}`}>
          {Math.round(score)}
          <span className="text-xs font-normal text-gray-400">/{maxScore}</span>
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/70">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
