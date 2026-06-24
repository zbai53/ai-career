import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { FileEdit, MessageSquare, AlertCircle, BarChart2, Loader2 } from 'lucide-react'
import RadarChart from '../components/RadarChart'
import ScoreCard from '../components/ScoreCard'
import GapAnalysis from '../components/GapAnalysis'
import EmptyState from '../components/EmptyState'
import { useGetMatch, useStartInterview } from '../api/hooks'
import { useWorkflowStore } from '../stores/workflowStore'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** gapAnalysis on the Spring Boot entity is stored as the raw JSON string
 *  from the Python agent response — parse it defensively. */
function parseGapAnalysis(raw: string | Record<string, unknown>): Record<string, unknown> {
  if (typeof raw === 'object' && raw !== null) return raw
  try { return JSON.parse(raw as string) } catch { return {} }
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="flex flex-col gap-6 sm:flex-row">
        <div className="h-56 w-full rounded-xl bg-gray-200 sm:max-w-xs" />
        <div className="flex-1 space-y-3 pt-4">
          <div className="h-16 rounded-lg bg-gray-200" />
          <div className="h-6 w-1/3 rounded bg-gray-200" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="h-20 rounded-xl bg-gray-200" />)}
      </div>
      <div className="h-64 rounded-xl bg-gray-200" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MatchResultPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentResumeId, currentJDId, setMatchId, setInterviewId } = useWorkflowStore()

  const matchId = id === 'latest' ? null : Number(id)
  const { data, isPending, isError, error } = useGetMatch(matchId)
  const startInterview = useStartInterview()

  // Persist match id to store once when the URL param changes — not on every render.
  // Using the URL `id` (a stable string) as the dependency avoids an infinite loop
  // that would occur if we called setMatchId unconditionally during render.
  useEffect(() => {
    if (matchId) setMatchId(matchId)
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- 404 ----
  if (isError) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-8 w-8" />}
        title="Match not found"
        description={error?.message ?? `No match result with id ${id}.`}
        actionLabel="Run a new match"
        onAction={() => navigate('/jd')}
      />
    )
  }

  // ---- No id yet (navigated via sidebar before running a match) ----
  if (id === 'latest' && !data) {
    return (
      <EmptyState
        icon={<BarChart2 className="h-8 w-8" />}
        title="No match results yet"
        description="Upload a resume and paste a JD to score how well you match the role."
        actionLabel="Get started"
        onAction={() => navigate('/upload')}
      />
    )
  }

  if (isPending) return <div className="mx-auto max-w-2xl"><Skeleton /></div>

  if (!data) return null

  // gapAnalysis is stored as the full Python response JSON string.
  // ATS fields live inside it, not as top-level entity fields.
  const gap = parseGapAnalysis(data.gapAnalysis ?? '')

  const overall = Number(data.overallScore)    || 0
  const skill   = Number(data.skillScore)      || 0
  const exp     = Number(data.experienceScore) || 0
  const keyword = Number(data.keywordScore)    || 0

  // ATS data is embedded in the parsed gap object
  const atsMissing = (gap.ats_missing  as string[] | undefined) ?? []
  const atsCov     = Number(gap.ats_coverage_percent) || 0

  const needsRewrite = overall < 70

  function handleStartInterview() {
    if (!currentResumeId || !currentJDId) return
    startInterview.mutate(
      { resumeId: currentResumeId, jdId: currentJDId },
      {
        onSuccess: (session) => {
          setInterviewId(session.sessionId)
          navigate(`/interview/${session.sessionId}`)
        },
      }
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Match Results</h1>

      {/* Radar + overall score */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <RadarChart
          skillScore={skill}
          experienceScore={exp}
          keywordScore={keyword}
          overallScore={overall}
        />
      </div>

      {/* Score cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ScoreCard label="Skill Score"       score={skill}   />
        <ScoreCard label="Experience Score"  score={exp}     />
        <ScoreCard label="Keyword Score"     score={keyword} />
        <ScoreCard label="ATS Coverage"      score={atsCov}  />
      </div>

      {/* ATS badges */}
      {atsMissing.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">
            ATS keywords missing from your resume ({atsMissing.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {atsMissing.map((kw) => (
              <span
                key={kw}
                className="inline-block rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Gap Analysis */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Gap Analysis</h2>
        <GapAnalysis gapAnalysis={gap} />
      </section>

      {/* Action buttons */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          onClick={() => navigate(`/rewrite/${data.id}`)}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition-colors ${
            needsRewrite
              ? 'bg-indigo-600 text-white hover:bg-indigo-700'
              : 'border border-indigo-300 text-indigo-700 hover:bg-indigo-50'
          }`}
        >
          <FileEdit className="h-4 w-4" />
          {needsRewrite ? 'Rewrite Resume (Recommended)' : 'Rewrite Resume'}
        </button>

        <button
          onClick={handleStartInterview}
          disabled={!currentResumeId || !currentJDId || startInterview.isPending}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {startInterview.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <MessageSquare className="h-4 w-4" />
          )}
          Practice Interview
        </button>
      </div>
    </div>
  )
}
