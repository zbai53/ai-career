import { useParams, useNavigate } from 'react-router-dom'
import { FileEdit, MessageSquare, AlertCircle } from 'lucide-react'
import RadarChart from '../components/RadarChart'
import ScoreCard from '../components/ScoreCard'
import GapAnalysis from '../components/GapAnalysis'
import { useGetMatch } from '../api/hooks'
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
  const { currentResumeId, currentJDId, setMatchId } = useWorkflowStore()

  const matchId = id === 'latest' ? null : Number(id)
  const { data, isPending, isError, error } = useGetMatch(
    id === 'latest' ? null : matchId
  )

  // Persist match id to store whenever we land on this page with a real id
  if (data?.id && matchId) setMatchId(data.id)

  // ---- 404 ----
  if (isError) {
    return (
      <div className="mx-auto max-w-lg space-y-4 pt-12 text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-red-400" />
        <h1 className="text-xl font-bold text-gray-900">Match not found</h1>
        <p className="text-sm text-gray-500">
          {error?.message ?? `No match result with id ${id}.`}
        </p>
        <button
          onClick={() => navigate('/jd')}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          Run a new match
        </button>
      </div>
    )
  }

  // ---- No id yet (navigated via sidebar before running a match) ----
  if (id === 'latest' && !data) {
    return (
      <div className="mx-auto max-w-lg space-y-4 pt-12 text-center">
        <h1 className="text-2xl font-bold text-gray-900">Match Results</h1>
        <p className="text-gray-500">
          No match result yet. Upload a resume and paste a JD to get started.
        </p>
        <button
          onClick={() => navigate('/upload')}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          Get started
        </button>
      </div>
    )
  }

  if (isPending) return <div className="mx-auto max-w-2xl"><Skeleton /></div>

  if (!data) return null

  const gapRaw = (data as unknown as { gapAnalysis: string | Record<string, unknown> }).gapAnalysis
  const gap    = parseGapAnalysis(gapRaw ?? {})

  const overall   = Number(data.overallScore)   || 0
  const skill     = Number(data.skillScore)      || 0
  const exp       = Number(data.experienceScore) || 0
  const keyword   = Number(data.keywordScore)    || 0
  const atsCov    = Number(data.ats_coverage_percent) || 0

  const needsRewrite = overall < 70

  // For interview navigation we need a session id — start from /jd to create one
  const interviewTarget = '/jd'

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
      {data.ats_missing?.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">
            ATS keywords missing from your resume ({data.ats_missing.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {data.ats_missing.map((kw) => (
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
          onClick={() => navigate(interviewTarget)}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          <MessageSquare className="h-4 w-4" />
          Practice Interview
        </button>
      </div>
    </div>
  )
}
