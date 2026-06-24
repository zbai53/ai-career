import { AlertCircle, Lightbulb, Target, Info } from 'lucide-react'

interface GapAnalysisProps {
  gapAnalysis: Record<string, unknown>
}

function strArr(obj: Record<string, unknown>, key: string): string[] {
  const v = obj[key]
  if (!Array.isArray(v)) return []
  return v.filter((x): x is string => typeof x === 'string')
}

function str(obj: Record<string, unknown>, key: string): string {
  const v = obj[key]
  return typeof v === 'string' ? v : ''
}

function Badge({ label, variant }: { label: string; variant: 'red' | 'orange' }) {
  const cls =
    variant === 'red'
      ? 'bg-red-100 text-red-700 ring-1 ring-red-200'
      : 'bg-orange-100 text-orange-700 ring-1 ring-orange-200'
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

export default function GapAnalysis({ gapAnalysis }: GapAnalysisProps) {
  const missingRequired  = strArr(gapAnalysis, 'missing_required_skills')
  const missingPreferred = strArr(gapAnalysis, 'missing_preferred_skills')
  const suggestions      = strArr(gapAnalysis, 'improvement_suggestions')
  const focusAreas       = strArr(gapAnalysis, 'interview_focus_areas')
  const assessment       = str(gapAnalysis, 'overall_assessment')

  const isEmpty =
    missingRequired.length === 0 &&
    missingPreferred.length === 0 &&
    suggestions.length === 0 &&
    focusAreas.length === 0 &&
    !assessment

  if (isEmpty) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-500">
        No gap analysis data available for this match.
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Missing required skills */}
      {missingRequired.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            <h3 className="text-sm font-semibold text-gray-800">
              Missing Required Skills
              <span className="ml-1.5 text-xs font-normal text-gray-400">
                ({missingRequired.length})
              </span>
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {missingRequired.map((s) => <Badge key={s} label={s} variant="red" />)}
          </div>
        </section>
      )}

      {/* Missing preferred skills */}
      {missingPreferred.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Info className="h-4 w-4 text-orange-500 shrink-0" />
            <h3 className="text-sm font-semibold text-gray-800">
              Missing Preferred Skills
              <span className="ml-1.5 text-xs font-normal text-gray-400">
                ({missingPreferred.length})
              </span>
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {missingPreferred.map((s) => <Badge key={s} label={s} variant="orange" />)}
          </div>
        </section>
      )}

      {/* Improvement suggestions */}
      {suggestions.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb className="h-4 w-4 text-indigo-500 shrink-0" />
            <h3 className="text-sm font-semibold text-gray-800">Improvement Suggestions</h3>
          </div>
          <ol className="space-y-2">
            {suggestions.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-700">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
                  {i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Interview focus areas */}
      {focusAreas.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-4 w-4 text-purple-500 shrink-0" />
            <h3 className="text-sm font-semibold text-gray-800">Interview Focus Areas</h3>
          </div>
          <ul className="space-y-1.5">
            {focusAreas.map((area, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-400" />
                {area}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Overall assessment */}
      {assessment && (
        <section className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
            Overall Assessment
          </p>
          <p className="text-sm text-gray-700 leading-relaxed">{assessment}</p>
        </section>
      )}
    </div>
  )
}
