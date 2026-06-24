interface TechnicalAnalysisProps {
  accuracy: number
  depth: number
  practical: number
  feedback: string
}

const BARS = [
  { key: 'accuracy' as const,  label: 'Accuracy',             description: 'Correctness of technical facts' },
  { key: 'depth'    as const,  label: 'Depth',                 description: 'Beyond surface-level explanation' },
  { key: 'practical' as const, label: 'Practical Experience',  description: 'Connection to real-world work' },
]

function barColor(score: number): string {
  if (score >= 8) return 'bg-indigo-500'
  if (score >= 5) return 'bg-yellow-500'
  return 'bg-red-500'
}

function textColor(score: number): string {
  if (score >= 8) return 'text-indigo-700'
  if (score >= 5) return 'text-yellow-700'
  return 'text-red-700'
}

export default function TechnicalAnalysis({ accuracy, depth, practical, feedback }: TechnicalAnalysisProps) {
  const values: Record<typeof BARS[number]['key'], number> = { accuracy, depth, practical }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {BARS.map(({ key, label, description }) => {
          const score = values[key]
          const pct   = (score / 10) * 100
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <div>
                  <span className="text-sm font-semibold text-gray-800">{label}</span>
                  <span className="ml-2 text-xs text-gray-400">{description}</span>
                </div>
                <span className={`text-sm font-bold tabular-nums ${textColor(score)}`}>
                  {score.toFixed(1)}<span className="text-xs font-normal text-gray-400">/10</span>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-100">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${barColor(score)}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {feedback && (
        <p className="rounded-lg bg-gray-50 px-4 py-3 text-sm leading-relaxed text-gray-600 border border-gray-200">
          {feedback}
        </p>
      )}
    </div>
  )
}
