import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, Star, Loader2, AlertCircle, MessageSquare } from 'lucide-react'
import ChatBubble, { TypingIndicator } from '../components/ChatBubble'
import ScoreBadge from '../components/ScoreBadge'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useGetInterview, useAnswerInterview, useEndInterview } from '../api/hooks'

// ---------------------------------------------------------------------------
// Types — mirror Python InterviewSessionData / AnswerEvaluation
// ---------------------------------------------------------------------------

interface InterviewQuestion {
  text: string
  type: string
  difficulty: string
  category: string
}

interface AnswerEvaluation {
  question: string
  answer: string
  relevance_score: number
  depth_score: number
  communication_score: number
  overall_score: number
  strengths: string[]
  improvements: string[]
  follow_up: string | null
}

interface ConversationTurn {
  role: 'interviewer' | 'candidate'
  content: string
  turn_number: number
}

interface SessionData {
  session_id: string
  jd_title: string
  questions: InterviewQuestion[]
  answers: AnswerEvaluation[]
  current_question_index: number
  status: string
  started_at: string
  conversation_history: ConversationTurn[]
}

function parseSession(raw: unknown): SessionData | null {
  if (!raw || typeof raw !== 'object') return null
  return raw as SessionData
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const cls =
    difficulty === 'hard'   ? 'bg-red-100    text-red-700'    :
    difficulty === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-green-100  text-green-700'
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${cls}`}>
      {difficulty}
    </span>
  )
}

function TypeBadge({ type }: { type: string }) {
  const cls = type === 'technical'
    ? 'bg-indigo-100 text-indigo-700'
    : 'bg-purple-100 text-purple-700'
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${cls}`}>
      {type}
    </span>
  )
}

function EvaluationCard({ eval: ev }: { eval: AnswerEvaluation }) {
  return (
    <div className="mx-9 my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-4">
      {/* Scores */}
      <div className="grid grid-cols-4 gap-2">
        <ScoreBadge label="Relevance"  score={ev.relevance_score} />
        <ScoreBadge label="Depth"      score={ev.depth_score} />
        <ScoreBadge label="Comm."      score={ev.communication_score} />
        <ScoreBadge label="Overall"    score={ev.overall_score} />
      </div>

      {/* Strengths */}
      {ev.strengths.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Strengths</p>
          <ul className="space-y-1">
            {ev.strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-500" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Improvements */}
      {ev.improvements.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Improvements</p>
          <ul className="space-y-1">
            {ev.improvements.map((imp, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-500" />
                {imp}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>()   // UUID string from the URL
  const navigate = useNavigate()

  // id IS the UUID session_id — no numeric conversion
  const { data: entity, isPending: loadingSession, isError } = useGetInterview(id ?? null)

  // Parse session data from the Python agent_state in the GET response
  const [sessionData, setSessionData] = useState<SessionData | null>(null)

  useEffect(() => {
    if (entity?.agent_state) {
      const parsed = parseSession(entity.agent_state)
      if (parsed) setSessionData(parsed)
    }
  }, [entity])

  // UUID for mutations is the URL param itself
  const sessionUUID = id ?? ''

  const answerMutation = useAnswerInterview(sessionUUID)
  const endMutation    = useEndInterview(sessionUUID)

  const [answer,         setAnswer]         = useState('')
  const [showEndDialog,  setShowEndDialog]  = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const MAX_CHARS = 2000

  // Auto-scroll on new messages or typing indicator
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [sessionData?.conversation_history.length, answerMutation.isPending])

  // Update local session when mutation returns updated Python agent state.
  // Answer/end responses are the raw Python state (not wrapped), so parse directly.
  function handleMutationSuccess(updated: Record<string, unknown>) {
    const parsed = parseSession(updated)
    if (parsed) setSessionData(parsed)
  }

  function handleSubmit() {
    if (!answer.trim() || answerMutation.isPending) return
    const text = answer.trim()
    setAnswer('')
    answerMutation.mutate(
      { answer: text },
      { onSuccess: (data) => handleMutationSuccess(data) }
    )
  }

  function handleEnd() {
    setShowEndDialog(true)
  }

  function confirmEnd() {
    setShowEndDialog(false)
    endMutation.mutate(undefined, {
      onSuccess: (data) => {
        handleMutationSuccess(data)
        navigate(`/review/${id}`)   // id is the UUID from URL params
      },
    })
  }

  // ---- Loading / error guards ----
  if (!id) {
    return (
      <EmptyState
        icon={<MessageSquare className="h-8 w-8" />}
        title="No active interview session"
        description="Start an interview from the Match Results page after uploading a resume and JD."
        actionLabel="Get started"
        onAction={() => navigate('/upload')}
      />
    )
  }

  if (isError) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-8 w-8" />}
        title="Session not found"
        description={`No interview session with id ${id}.`}
        actionLabel="Go back"
        onAction={() => navigate(-1)}
      />
    )
  }

  if (loadingSession || !sessionData) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    )
  }

  const { questions, answers, conversation_history, current_question_index, status, jd_title } = sessionData

  const isCompleted = status === 'completed'
  const currentQ    = questions[Math.min(current_question_index, questions.length - 1)]
  const totalQ      = questions.length
  const answeredQ   = answers.length

  // Build evaluation map: nth candidate message → evaluation
  const candidateTurns = conversation_history.filter((t) => t.role === 'candidate')
  const evalByTurnIdx  = new Map(answers.map((ev, i) => [i, ev]))

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <ConfirmDialog
        isOpen={showEndDialog}
        title="End interview?"
        message="This will end your current session. You will be taken to the review page."
        confirmLabel="End Interview"
        onConfirm={confirmEnd}
        onCancel={() => setShowEndDialog(false)}
      />
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div className="flex shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">{jd_title || 'Mock Interview'}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-gray-500">
              Question {Math.min(answeredQ + 1, totalQ)} of {totalQ}
            </span>
            {currentQ && (
              <>
                <DifficultyBadge difficulty={currentQ.difficulty} />
                <TypeBadge type={currentQ.type} />
              </>
            )}
          </div>
        </div>

        <button
          onClick={handleEnd}
          disabled={endMutation.isPending || isCompleted}
          className="shrink-0 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {endMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : 'End Interview'}
        </button>
      </div>

      {/* ── Chat area ───────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto bg-gray-50 px-4 py-6 space-y-4">
        {conversation_history.map((turn, idx) => {
          const isCandidateTurn = turn.role === 'candidate'
          // Find which nth candidate message this is to look up evaluation
          const candidateIdx = isCandidateTurn
            ? candidateTurns.findIndex((t) => t === turn)
            : -1
          const evaluation = candidateIdx >= 0 ? evalByTurnIdx.get(candidateIdx) : undefined

          return (
            <div key={idx}>
              <ChatBubble
                role={turn.role}
                content={turn.content}
                timestamp={sessionData.started_at ? undefined : undefined}
              />
              {/* Inline evaluation card after candidate messages */}
              {isCandidateTurn && evaluation && (
                <EvaluationCard eval={evaluation} />
              )}
            </div>
          )
        })}

        {/* Typing indicator while awaiting response */}
        {answerMutation.isPending && <TypingIndicator />}

        {/* Interview complete banner */}
        {isCompleted && (
          <div className="mx-auto max-w-sm rounded-xl border border-green-200 bg-green-50 p-5 text-center space-y-3">
            <Star className="mx-auto h-8 w-8 text-green-500" />
            <p className="font-semibold text-green-800">Interview Complete!</p>
            <button
              onClick={() => navigate(`/review/${id}`)}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"
            >
              View Review
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ──────────────────────────────────────────────────── */}
      {!isCompleted && (
        <div className="shrink-0 border-t border-gray-200 bg-white p-4 space-y-2">
          {answerMutation.isError && (
            <p className="flex items-center gap-1.5 text-xs text-red-600">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {answerMutation.error?.message ?? 'Failed to submit answer. Try again.'}
            </p>
          )}

          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value.slice(0, MAX_CHARS))}
            placeholder="Type your answer here…"
            rows={4}
            disabled={answerMutation.isPending}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
            }}
            className="w-full resize-none rounded-xl border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-60"
          />

          <div className="flex items-center justify-between">
            <span className={`text-xs ${answer.length >= MAX_CHARS * 0.9 ? 'text-red-500' : 'text-gray-400'}`}>
              {answer.length}/{MAX_CHARS}
            </span>
            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-gray-400 sm:block">⌘ Enter to submit</span>
              <button
                onClick={handleSubmit}
                disabled={!answer.trim() || answerMutation.isPending}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {answerMutation.isPending ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Evaluating…</>
                ) : (
                  'Submit Answer'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
