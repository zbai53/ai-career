import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
// Types — mirror Python CoachReview model
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
}

interface SessionData {
  questions: Array<{ text: string; type: string; difficulty: string }>
  answers: AnswerEvaluation[]
}

function parseReview(raw: Record<string, unknown> | null): CoachReview | null {
  if (!raw) return null
  return raw as unknown as CoachReview
}

function parseSession(raw: Record<string, unknown>): SessionData | null {
  if (!raw) return null
  return raw as unknown as SessionData
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

          {/* STAR or Technical analysis */}
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

  // id is the UUID session_id — use it directly (no numeric conversion)
  const sessionId = id === 'latest' ? null : (id ?? null)
  const { data: entity, isPending, isError } = useGetInterview(sessionId)

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

  // agent_state is the full Python session state; it contains both the coach
  // review (under the "review" key) and the conversation/question data.
  const agentState = entity.agent_state ?? {}
  const review  = parseReview(agentState.review as Record<string, unknown> | null)
  const session = parseSession(agentState as Record<string, unknown>)

  if (!review) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-8 w-8" />}
        title="Review not ready"
        description="The coach review hasn't been generated yet. End the interview to receive AI coaching feedback."
        actionLabel="Return to interview"
        onAction={() => navigate(`/interview/${sessionId}`)}
      />
    )
  }

  const questions   = session?.questions ?? []
  const answers     = session?.answers   ?? []

  // Build a lookup: question text → AnswerEvaluation
  const evalByQ = new Map(answers.map((a) => [a.question, a]))

  // Build per-question data list
  const behavioralByQ = new Map(review.behavioral_reviews.map((r) => [r.question, r]))
  const technicalByQ  = new Map(review.technical_reviews.map((r)  => [r.question, r]))

  return (
    <div className="mx-auto max-w-2xl space-y-10 pb-16">
      <h1 className="text-2xl font-bold text-gray-900">Interview Review</h1>

      {/* ── Overall score + readiness ──────────────────────────────────── */}
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
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
      </section>

      {/* ── Strengths ─────────────────────────────────────────────────── */}
      {review.top_strengths.length > 0 && (
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

      {/* ── Areas for improvement ──────────────────────────────────────── */}
      {review.areas_for_improvement.length > 0 && (
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
      {questions.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-gray-900">
            Question-by-Question Breakdown
          </h2>
          <div className="space-y-3">
            {questions.map((q, i) => {
              const evalScores = evalByQ.get(q.text)
              const behavioral = behavioralByQ.get(q.text)
              const technical  = technicalByQ.get(q.text)
              const answerText = evalScores?.answer ?? ''
              return (
                <AccordionItem
                  key={i}
                  question={q.text}
                  answer={answerText}
                  qType={q.type}
                  qDifficulty={q.difficulty}
                  behavioral={behavioral}
                  technical={technical}
                  evalScores={evalScores}
                  defaultOpen={i === 0}
                />
              )
            })}
          </div>
        </section>
      )}

      {/* ── Communication review ───────────────────────────────────────── */}
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

      {/* ── Recommended topics ──────────────────────────────────────────── */}
      {review.recommended_topics.length > 0 && (
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
