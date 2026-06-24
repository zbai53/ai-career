import { useParams, useNavigate } from 'react-router-dom'
import { MessageSquare, CheckSquare, AlertCircle, TrendingUp, Zap, FileText } from 'lucide-react'
import FidelityBadge from '../components/FidelityBadge'
import BulletComparison from '../components/BulletComparison'
import EmptyState from '../components/EmptyState'
import { useGetRewrite } from '../api/hooks'

// ---------------------------------------------------------------------------
// Types matching Python RewriteResult / ImprovementMetrics models
// ---------------------------------------------------------------------------

interface RewrittenBullet {
  original: string
  rewritten: string
  changes_made: string[]
}

interface RewrittenExperience {
  company: string
  title: string
  original_bullets: string[]
  rewritten_bullets: RewrittenBullet[]
}

interface ImprovementMetrics {
  keywords_added: string[]
  keywords_removed: string[]
  avg_bullet_length_change: number
  action_verbs_improved: number
}

interface FidelityReport {
  fidelity_score: number
  passed: boolean
  flags: Array<{ entity: string; entity_type: string; severity: string }>
  new_entities_found: number
}

interface RewriteData {
  experiences: RewrittenExperience[]
  keywords_injected: string[]
  overall_improvement_summary: string
  rewrite_attempts: number
  fidelity_report: FidelityReport | null
  fidelity_status: string
  improvement_metrics: ImprovementMetrics | null
}

function parseRewriteData(raw: string): RewriteData | null {
  try { return JSON.parse(raw) } catch { return null }
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="flex items-center gap-4">
        <div className="h-9 w-28 rounded-lg bg-gray-200" />
        <div className="h-5 w-24 rounded bg-gray-200" />
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="space-y-3">
          <div className="h-6 w-48 rounded bg-gray-200" />
          <div className="h-32 rounded-xl bg-gray-200" />
          <div className="h-32 rounded-xl bg-gray-200" />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Small sub-components
// ---------------------------------------------------------------------------

function MetricTag({
  label,
  variant,
}: {
  label: string
  variant: 'green' | 'red'
}) {
  const cls =
    variant === 'green'
      ? 'bg-green-100 text-green-700 ring-1 ring-green-200'
      : 'bg-red-100 text-red-700 ring-1 ring-red-200'
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

function MetricStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-gray-50 p-3 text-center">
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RewritePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const rewriteId = id === 'latest' ? null : Number(id)
  const { data: entity, isPending, isError, error } = useGetRewrite(rewriteId)

  // ---- No id yet ----
  if (id === 'latest' || !rewriteId) {
    return (
      <EmptyState
        icon={<FileText className="h-8 w-8" />}
        title="No rewrite yet"
        description="Run a match first and click 'Rewrite Resume' to see an AI-improved version of your resume."
        actionLabel="Get started"
        onAction={() => navigate('/upload')}
      />
    )
  }

  if (isError) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-8 w-8" />}
        title="Rewrite not found"
        description={error?.message ?? `No rewrite result with id ${id}.`}
        actionLabel="Go back"
        onAction={() => navigate(-1)}
      />
    )
  }

  if (isPending) return <div className="mx-auto max-w-3xl"><Skeleton /></div>
  if (!entity) return null

  const rd = parseRewriteData(entity.rewriteData)
  if (!rd) {
    return (
      <div className="mx-auto max-w-lg pt-12 text-center text-sm text-gray-500">
        Could not parse rewrite data.
      </div>
    )
  }

  const fidelityScore = rd.fidelity_report?.fidelity_score ?? entity.fidelityScore ?? null
  const fidelityPassed = rd.fidelity_report?.passed ?? entity.fidelityStatus === 'passed'
  const metrics = rd.improvement_metrics
  const lengthChangePct = metrics
    ? `${metrics.avg_bullet_length_change >= 0 ? '+' : ''}${(metrics.avg_bullet_length_change * 100).toFixed(0)}%`
    : '—'

  const totalBullets = rd.experiences.reduce(
    (sum, exp) => sum + exp.rewritten_bullets.length, 0
  )

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Resume Rewrite</h1>

      {/* Top meta strip */}
      <div className="flex flex-wrap items-center gap-3">
        <FidelityBadge score={fidelityScore} passed={fidelityPassed} />

        <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
          <Zap className="h-4 w-4 text-indigo-500" />
          <span>{rd.rewrite_attempts} attempt{rd.rewrite_attempts !== 1 ? 's' : ''}</span>
        </div>

        <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
          <TrendingUp className="h-4 w-4 text-green-500" />
          <span>{rd.keywords_injected.length} keyword{rd.keywords_injected.length !== 1 ? 's' : ''} injected</span>
        </div>

        <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
          <CheckSquare className="h-4 w-4 text-gray-400" />
          <span>{totalBullets} bullet{totalBullets !== 1 ? 's' : ''} rewritten</span>
        </div>
      </div>

      {/* Experience sections */}
      {rd.experiences.map((exp, ei) => (
        <section key={ei} className="space-y-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{exp.company}</h2>
            <p className="text-sm text-gray-500">{exp.title}</p>
          </div>

          {exp.rewritten_bullets.map((bullet, bi) => (
            <BulletComparison
              key={bi}
              original={bullet.original}
              rewritten={bullet.rewritten}
              changes={bullet.changes_made}
              keywordsInjected={rd.keywords_injected}
            />
          ))}
        </section>
      ))}

      {/* Improvement metrics */}
      {metrics && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Improvement Metrics</h2>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricStat label="Keywords added"   value={String(metrics.keywords_added.length)} />
            <MetricStat label="Keywords removed" value={String(metrics.keywords_removed.length)} />
            <MetricStat label="Avg length change" value={lengthChangePct} />
            <MetricStat label="Verbs improved"   value={String(metrics.action_verbs_improved)} />
          </div>

          {metrics.keywords_added.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Keywords added
              </p>
              <div className="flex flex-wrap gap-2">
                {metrics.keywords_added.map((k) => <MetricTag key={k} label={k} variant="green" />)}
              </div>
            </div>
          )}

          {metrics.keywords_removed.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Keywords removed
              </p>
              <div className="flex flex-wrap gap-2">
                {metrics.keywords_removed.map((k) => <MetricTag key={k} label={k} variant="red" />)}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Overall summary */}
      {rd.overall_improvement_summary && (
        <section className="rounded-xl border border-gray-200 bg-gray-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
            Overall Improvement Summary
          </p>
          <p className="text-sm leading-relaxed text-gray-700">
            {rd.overall_improvement_summary}
          </p>
        </section>
      )}

      {/* Action buttons */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          onClick={() => alert('Accept Rewrite — will save the preferred version in Phase 7')}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          <CheckSquare className="h-4 w-4" />
          Accept Rewrite
        </button>

        <button
          onClick={() => navigate('/jd')}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          <MessageSquare className="h-4 w-4" />
          Practice Interview
        </button>
      </div>
    </div>
  )
}
