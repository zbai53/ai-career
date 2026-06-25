import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  CheckCircle2, AlertTriangle, BookOpen, ChevronDown,
  RotateCcw, LayoutDashboard, Loader2, AlertCircle, Trophy, Star,
} from 'lucide-react'
import STARAnalysis from '../components/STARAnalysis'
import TechnicalAnalysis from '../components/TechnicalAnalysis'
import ScoreBadge from '../components/ScoreBadge'
import EmptyState from '../components/EmptyState'
import { useGetInterview } from '../api/hooks'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface STARScore { situation: number; task: number; action: number; result: number }

interface BehavioralReview {
  question: string
  star_score: STARScore
  feedback: string
}

interface TechnicalReview {
  question: string
  accuracy: number
  depth: number
  practical: number
  feedback: string
}

interface CommunicationReview {
  clarity: number
  conciseness: number
  confidence: number
  feedback: string
}

interface CoachReview {
  overall_score: number
  behavioral_reviews: BehavioralReview[]
  technical_reviews: TechnicalReview[]
  communication: CommunicationReview
  top_strengths: string[]
  areas_for_improvement: string[]
  recommended_topics: string[]
  readiness: 'yes' | 'almost' | 'needs_more_practice'
  summary: string
}

interface AnswerEvaluation {
  question: string
  answer: string
  relevance_score: number
  depth_score: number
  communication_score: number
  overall_score: number
  strengths?: string[]
  improvements?: string[]
}

interface QuestionMeta {
  text: string
  type: string
  difficulty: string
}

interface AverageScores {
  relevance: number
  depth: number
  communication: number
  overall: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseReview(raw: Record<string, unknown> | null | undefined): CoachReview | null {
  if (!raw) return null
  return raw as unknown as CoachReview
}

/** Parse questions from either end-response (`questions`) or GET agent_state (`questions_asked`). */
function parseQuestions(source: Record<string, unknown>): QuestionMeta[] {
  const fromEnd = source.questions as Array<{ text: string; type: string; difficulty: string }> | undefined
  if (fromEnd && Array.isArray(fromEnd)) return fromEnd

  const fromGet = source.questions_asked as Array<{ text: string; type: string; difficulty: string }> | undefined
  if (fromGet && Array.isArray(fromGet)) return fromGet

  return []
}

/** Compute average scores from individual answer evaluations. */
function computeAverageScores(answers: AnswerEvaluation[]): AverageScores | null {
  if (answers.length === 0) return null
  const avg = (fn: (a: AnswerEvaluation) => number) =>
    Math.round((answers.reduce((s, a) => s + fn(a), 0) / answers.length) * 10) / 10
  return {
    relevance:     avg((a) => a.relevance_score),
    depth:         avg((a) => a.depth_score),
    communication: avg((a) => a.communication_score),
    overall:       avg((a) => a.overall_score),
  }
}

// ---------------------------------------------------------------------------
// Readiness badge
// ---------------------------------------------------------------------------

const READINESS_CONFIG = {
  yes: {
    label: 'Ready to Apply',
    classes: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    icon: Trophy,
  },
  almost: {
    label: 'Almost Ready',
    classes: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
    icon: AlertTriangle,
  },
  needs_more_practice: {
    label: 'Needs More Practice',
    classes: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    icon: AlertCircle,
  },
}

function ReadinessBadge({ readiness }: { readiness: CoachReview['readiness'] }) {
  const { label, classes, icon: Icon } = READINESS_CONFIG[readiness]
  return (
    <div className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 ${classes}`}>
      <Icon className="h-4 w-4" />
      <span className="text-sm font-semibold">{label}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Communication bar
// ---------------------------------------------------------------------------

function CommBar({ label, score }: { label: string; score: number }) {
  const pct = (score / 10) * 100
  const barCls = score >= 8 ? 'bg-green-500' : score >= 5 ? 'bg-yellow-500' : 'bg-red-500'
  const txtCls = score >= 8 ? 'text-green-700' : score >= 5 ? 'text-yellow-700' : 'text-red-700'
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-bold tabular-nums ${txtCls}`}>
          {score.toFixed(1)}<span className="text-xs font-normal text-gray-400">/10</span>
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-100">
        <div className={`h-2 rounded-full transition-all duration-500 ${barCls}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Accordion item
// ---------------------------------------------------------------------------

function AccordionItem({
  question, answer, qType, qDifficulty,
  behavioral, technical, evalScores, defaultOpen,
}: {
  question: string
  answer: string
  qType: string
  qDifficulty: string
  behavioral?: BehavioralReview
  technical?: TechnicalReview
  evalScores?: AnswerEvaluation
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen ?? false)

  const typeColor = qType === 'technical'
    ? 'bg-indigo-100 text-indigo-700'
    : 'bg-purple-100 text-purple-700'
  const diffColor = qDifficulty === 'hard'
    ? 'bg-red-100 text-red-700'
    : qDifficulty === 'medium'
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-green-100 text-green-700'

  const strengths    = evalScores?.strengths    ?? []
  const improvements = evalScores?.improvements ?? []

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <ChevronDown
          className={`mt-0.5 h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 leading-snug">{question}</p>
          <div className="mt-1.5 flex gap-1.5">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${typeColor}`}>
              {qType}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${diffColor}`}>
              {qDifficulty}
            </span>
          </div>
        </div>
        {evalScores && (
          <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-bold tabular-nums text-gray-600">
            {evalScores.overall_score.toFixed(1)}/10
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-5 space-y-5">
          {/* Candidate's answer */}
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Your answer</p>
            <p className="rounded-lg bg-gray-50 px-4 py-3 text-sm leading-relaxed text-gray-700 border border-gray-200">
              {answer || '(No answer recorded)'}
            </p>
          </div>

          {/* Score badges */}
          {evalScores && (
            <div className="grid grid-cols-4 gap-2">
              <ScoreBadge label="Relevance" score={evalScores.relevance_score} />
              <ScoreBadge label="Depth"     score={evalScores.depth_score} />
              <ScoreBadge label="Comm."     score={evalScores.communication_score} />
              <ScoreBadge label="Overall"   score={evalScores.overall_score} />
            </div>
          )}

          {/* Strengths from per-answer evaluation */}
          {strengths.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Strengths</p>
              <ul className="space-y-1">
                {strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Improvements from per-answer evaluation */}
          {improvements.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Improvements</p>
              <ul className="space-y-1">
                {improvements.map((imp, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-500" />
                    {imp}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* STAR or Technical analysis from coach review (when available) */}
          {behavioral && (
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">STAR Analysis</p>
              <STARAnalysis starScore={behavioral.star_score} feedback={behavioral.feedback} />
            </div>
          )}
          {technical && (
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Technical Analysis</p>
              <TechnicalAnalysis
                accuracy={technical.accuracy}
                depth={technical.depth}
                practical={technical.practical}
                feedback={technical.feedback}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function scoreColor(s: number): string {
  if (s >= 70) return 'text-green-600'
  if (s >= 50) return 'text-yellow-600'
  return 'text-red-600'
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  // Prefer data passed via route state from InterviewPage's /end response —
  // this avoids an extra GET fetch and is available immediately after ending.
  const endData = (location.state as { endData?: Record<string, unknown> } | null)?.endData

  const sessionId = id === 'latest' ? null : (id ?? null)

  // Only fetch from the API when we don't already have the end data in route state.
  const { data: entity, isPending, isError } = useGetInterview(endData ? null : sessionId)

  // ---- Guards ----
  if (!sessionId) {
    return (
      <EmptyState
        icon={<Star className="h-8 w-8" />}
        title="No review available"
        description="Complete a mock interview to receive detailed AI coaching feedback."
        actionLabel="Back to Dashboard"
        onAction={() => navigate('/')}
      />
    )
  }

  // Only block on loading/error when we need to fetch from GET
  if (!endData) {
    if (isPending) {
      return (
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      )
    }
    if (isError || !entity) {
      return (
        <EmptyState
          icon={<AlertCircle className="h-8 w-8" />}
          title="Review not found"
          description={`No interview session with id ${id}.`}
          actionLabel="Go back"
          onAction={() => navigate(-1)}
        />
      )
    }
  }

  // Resolve source data:
  //   endData  = Python /end response (has `questions`, `answers`, `average_scores` — no `review`)
  //   agent_state = Python GET response (has `questions_asked`, `answers` — no `review`)
  const sourceData: Record<string, unknown> =
    endData ?? (entity?.agent_state as Record<string, unknown> ?? {})

  // Parse fields — field names differ slightly between end response and GET agent_state
  const questions  = parseQuestions(sourceData)
  const answers    = ((sourceData.answers ?? []) as AnswerEvaluation[])
  const jdTitle    = (sourceData.jd_title as string | undefined) ?? ''

  // Average scores: end response provides them pre-computed; otherwise derive from answers
  const rawAvgScores = sourceData.average_scores as AverageScores | undefined
  const averageScores: AverageScores | null = rawAvgScores ?? computeAverageScores(answers)

  // Coach review is only present if CoachAgent was called (e.g. /end-with-review endpoint)
  const reviewRaw = (sourceData.review ?? sourceData.coach_review) as Record<string, unknown> | null | undefined
  const review = parseReview(reviewRaw)

  // If we have no data at all, show an appropriate empty state
  if (answers.length === 0 && questions.length === 0) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-8 w-8" />}
        title="No answers recorded"
        description="Answer at least one question before ending the interview to see your review."
        actionLabel="Return to interview"
        onAction={() => navigate(`/interview/${sessionId}`)}
      />
    )
  }

  // Build lookups for optional coach review data
  const behavioralByQ  = new Map((review?.behavioral_reviews ?? []).map((r) => [r.question, r]))
  const technicalByQ   = new Map((review?.technical_reviews  ?? []).map((r) => [r.question, r]))
  const questionsByText = new Map(questions.map((q) => [q.text, q]))

  return (
    <div className="mx-auto max-w-2xl space-y-10 pb-16">
      <h1 className="text-2xl font-bold text-gray-900">Interview Review</h1>

      {/* ── Summary card ───────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {review ? (
          /* Full coach review: overall score (0–100) + readiness + summary */
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-8">
            <div className="text-center sm:text-left">
              <span className={`text-7xl font-extrabold leading-none tabular-nums ${scoreColor(review.overall_score)}`}>
                {Math.round(review.overall_score)}
              </span>
              <span className="ml-1 text-sm text-gray-400">/ 100</span>
            </div>
            <div className="space-y-2">
              <ReadinessBadge readiness={review.readiness} />
              {review.summary && (
                <p className="text-sm leading-relaxed text-gray-600 max-w-prose">{review.summary}</p>
              )}
            </div>
          </div>
        ) : averageScores ? (
          /* Fallback: average scores from the session (0–10 scale) */
          <div>
            <p className="mb-4 text-sm font-semibold text-gray-700">
              Average scores across {answers.length} answered question{answers.length !== 1 ? 's' : ''}
              {jdTitle ? ` — ${jdTitle}` : ''}
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <ScoreBadge label="Relevance"    score={averageScores.relevance} />
              <ScoreBadge label="Depth"        score={averageScores.depth} />
              <ScoreBadge label="Comm."        score={averageScores.communication} />
              <ScoreBadge label="Overall"      score={averageScores.overall} />
            </div>
          </div>
        ) : null}
      </section>

      {/* ── Top strengths (coach review only) ─────────────────────────── */}
      {review && review.top_strengths.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">Top Strengths</h2>
          <ul className="space-y-2">
            {review.top_strengths.slice(0, 3).map((s, i) => (
              <li key={i} className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                <span className="text-sm text-gray-700">{s}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Areas for improvement (coach review only) ──────────────────── */}
      {review && review.areas_for_improvement.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">Areas for Improvement</h2>
          <ul className="space-y-2">
            {review.areas_for_improvement.slice(0, 3).map((a, i) => (
              <li key={i} className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-600" />
                <span className="text-sm text-gray-700">{a}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Per-question accordion ──────────────────────────────────────── */}
      {answers.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">
            Question-by-Question Breakdown
          </h2>
          <div className="space-y-3">
            {answers.map((ans, i) => {
              const q          = questionsByText.get(ans.question)
              const behavioral = behavioralByQ.get(ans.question)
              const technical  = technicalByQ.get(ans.question)
              return (
                <AccordionItem
                  key={i}
                  question={ans.question}
                  answer={ans.answer ?? ''}
                  qType={q?.type ?? 'technical'}
                  qDifficulty={q?.difficulty ?? 'medium'}
                  behavioral={behavioral}
                  technical={technical}
                  evalScores={ans}
                  defaultOpen={i === 0}
                />
              )
            })}
          </div>
        </section>
      )}

      {/* ── Communication review (coach review only) ───────────────────── */}
      {review && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Communication</h2>
          <CommBar label="Clarity"     score={review.communication.clarity} />
          <CommBar label="Conciseness" score={review.communication.conciseness} />
          <CommBar label="Confidence"  score={review.communication.confidence} />
          {review.communication.feedback && (
            <p className="rounded-lg bg-gray-50 px-4 py-3 text-sm leading-relaxed text-gray-600 border border-gray-200">
              {review.communication.feedback}
            </p>
          )}
        </section>
      )}

      {/* ── Recommended topics (coach review only) ──────────────────────── */}
      {review && review.recommended_topics.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">Recommended Study Topics</h2>
          <div className="flex flex-wrap gap-2">
            {review.recommended_topics.map((topic, i) => (
              <div key={i} className="flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700">
                <BookOpen className="h-3.5 w-3.5 shrink-0" />
                {topic}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Actions ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          onClick={() => navigate('/jd')}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          <RotateCcw className="h-4 w-4" />
          Practice Again
        </button>
        <button
          onClick={() => navigate('/')}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          <LayoutDashboard className="h-4 w-4" />
          Back to Dashboard
        </button>
      </div>
    </div>
  )
}
