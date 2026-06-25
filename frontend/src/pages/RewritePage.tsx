import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { MessageSquare, CheckSquare, AlertCircle, TrendingUp, Zap, FileText, Loader2 } from 'lucide-react'
import FidelityBadge from '../components/FidelityBadge'
import BulletComparison from '../components/BulletComparison'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import { useStartInterview } from '../api/hooks'
import { useWorkflowStore } from '../stores/workflowStore'

// ---------------------------------------------------------------------------
// Types matching Python RewriteResult / ImprovementMetrics models
// ---------------------------------------------------------------------------

interface RewrittenBullet {
  original: string
  rewritten: string
  changes_made?: string[]
}

interface RewrittenExperience {
  company?: string
  title?: string
  original_bullets?: string[]
  rewritten_bullets?: RewrittenBullet[]
}

interface ImprovementMetrics {
  keywords_added?: string[]
  keywords_removed?: string[]
  avg_bullet_length_change?: number
  action_verbs_improved?: number
}

interface FidelityReport {
  fidelity_score?: number
  passed?: boolean
  flags?: Array<{ entity: string; entity_type: string; severity: string }>
  new_entities_found?: number
}

interface RewriteData {
  experiences?: RewrittenExperience[]
  keywords_injected?: string[]
  overall_improvement_summary?: string
  rewrite_attempts?: number
  rewrite_confidence?: number
  fidelity_report?: FidelityReport | null
  fidelity_status?: string
  improvement_metrics?: ImprovementMetrics | null
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricTag({ label, variant }: { label: string; variant: 'green' | 'red' }) {
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
  const location = useLocation()
  const { currentResumeId, currentJDId, setInterviewId } = useWorkflowStore()
  const startInterview = useStartInterview()

  // Route state contains the raw API response object — no JSON.parse needed
  const rd = location.state?.rewriteData as RewriteData | undefined

  // ---- No data in route state ----
  if (!rd) {
    return (
      <EmptyState
        icon={<FileText className="h-8 w-8" />}
        title="No rewrite data available"
        description="Run a match and click 'Rewrite Resume' to generate an AI-improved version of your resume."
        actionLabel={id && id !== 'latest' ? 'Back to match results' : 'Run a match'}
        onAction={() => (id && id !== 'latest' ? navigate(-1) : navigate('/jd'))}
      />
    )
  }

  const experiences      = rd.experiences ?? []
  const keywordsInjected = rd.keywords_injected ?? []
  const metrics          = rd.improvement_metrics ?? null
  const fidelityReport   = rd.fidelity_report ?? null
  const rewriteAttempts  = rd.rewrite_attempts ?? 1

  const fidelityScore  = fidelityReport?.fidelity_score ?? null
  const fidelityPassed = fidelityReport?.passed ?? false

  const lengthChangePct = metrics?.avg_bullet_length_change != null
    ? `${metrics.avg_bullet_length_change >= 0 ? '+' : ''}${(metrics.avg_bullet_length_change * 100).toFixed(0)}%`
    : '—'

  const totalBullets = experiences.reduce(
    (sum, exp) => sum + (exp.rewritten_bullets?.length ?? 0), 0
  )

  function handleStartInterview() {
    if (!currentResumeId || !currentJDId) return
    startInterview.mutate(
      { resumeId: currentResumeId, jdId: currentJDId, numQuestions: 5 },
      {
        onSuccess: (session) => {
          setInterviewId(session.session_id)
          navigate(`/interview/${session.session_id}`)
        },
      }
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        title="Resume Rewrite"
        subtitle="AI-optimised bullets with ATS keywords injected."
      />

      {/* Top meta strip */}
      <div className="flex flex-wrap items-center gap-3">
        <FidelityBadge score={fidelityScore} passed={fidelityPassed} />

        <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
          <Zap className="h-4 w-4 text-indigo-500" />
          <span>{rewriteAttempts} attempt{rewriteAttempts !== 1 ? 's' : ''}</span>
        </div>

        {keywordsInjected.length > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
            <TrendingUp className="h-4 w-4 text-green-500" />
            <span>{keywordsInjected.length} keyword{keywordsInjected.length !== 1 ? 's' : ''} injected</span>
          </div>
        )}

        {totalBullets > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-600">
            <CheckSquare className="h-4 w-4 text-gray-400" />
            <span>{totalBullets} bullet{totalBullets !== 1 ? 's' : ''} rewritten</span>
          </div>
        )}
      </div>

      {/* Experience sections */}
      {experiences.length > 0 ? (
        experiences.map((exp, ei) => (
          <section key={ei} className="space-y-4">
            {(exp.company || exp.title) && (
              <div>
                {exp.company && <h2 className="text-base font-semibold text-gray-900">{exp.company}</h2>}
                {exp.title   && <p className="text-sm text-gray-500">{exp.title}</p>}
              </div>
            )}

            {(exp.rewritten_bullets ?? []).map((bullet, bi) => (
              <BulletComparison
                key={bi}
                original={bullet.original}
                rewritten={bullet.rewritten}
                changes={bullet.changes_made ?? []}
                keywordsInjected={keywordsInjected}
              />
            ))}
          </section>
        ))
      ) : (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-500">
          No experience sections found in the rewrite result.
        </div>
      )}

      {/* Keywords injected */}
      {keywordsInjected.length > 0 && (
        <section className="rounded-xl border border-green-200 bg-green-50 p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-green-700">
            Keywords injected ({keywordsInjected.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {keywordsInjected.map((kw) => (
              <span
                key={kw}
                className="inline-block rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 ring-1 ring-green-200"
              >
                {kw}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Improvement metrics */}
      {metrics && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Improvement Metrics</h2>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricStat label="Keywords added"    value={String(metrics.keywords_added?.length    ?? 0)} />
            <MetricStat label="Keywords removed"  value={String(metrics.keywords_removed?.length  ?? 0)} />
            <MetricStat label="Avg length change" value={lengthChangePct} />
            <MetricStat label="Verbs improved"    value={String(metrics.action_verbs_improved     ?? 0)} />
          </div>

          {(metrics.keywords_added?.length ?? 0) > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Keywords added</p>
              <div className="flex flex-wrap gap-2">
                {metrics.keywords_added!.map((k) => <MetricTag key={k} label={k} variant="green" />)}
              </div>
            </div>
          )}

          {(metrics.keywords_removed?.length ?? 0) > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Keywords removed</p>
              <div className="flex flex-wrap gap-2">
                {metrics.keywords_removed!.map((k) => <MetricTag key={k} label={k} variant="red" />)}
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

      {/* Fidelity flags */}
      {(fidelityReport?.flags?.length ?? 0) > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
            Fidelity flags ({fidelityReport!.flags!.length})
          </p>
          <div className="space-y-2">
            {fidelityReport!.flags!.map((flag, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  flag.severity === 'high'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-amber-100 text-amber-700'
                }`}>
                  {flag.severity}
                </span>
                <span className="text-amber-800">
                  <span className="font-medium">{flag.entity}</span>
                  {flag.entity_type && <span className="text-amber-600"> ({flag.entity_type})</span>}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Action buttons */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          onClick={handleStartInterview}
          disabled={!currentResumeId || !currentJDId || startInterview.isPending}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
        >
          {startInterview.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <MessageSquare className="h-4 w-4" />
          )}
          Practice Interview
        </button>

        <button
          onClick={() => navigate(-1)}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Back to Match Results
        </button>
      </div>
    </div>
  )
}
