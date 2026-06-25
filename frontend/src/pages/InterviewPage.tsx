import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, Star, Loader2, AlertCircle, MessageSquare } from 'lucide-react'
import ChatBubble, { TypingIndicator } from '../components/ChatBubble'
import TypewriterText from '../components/TypewriterText'
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

function EvaluationCard({ eval: ev }: { eval: EvaluationData }) {
  const strengths    = ev.strengths    ?? []
  const improvements = ev.improvements ?? []

  return (
    <div className="mx-9 my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-4">
      {/* Scores */}
      <div className="grid grid-cols-4 gap-2">
        <ScoreBadge label="Relevance"  score={ev.relevance_score    ?? 0} />
        <ScoreBadge label="Depth"      score={ev.depth_score        ?? 0} />
        <ScoreBadge label="Comm."      score={ev.communication_score ?? 0} />
        <ScoreBadge label="Overall"    score={ev.overall_score      ?? 0} />
      </div>

      {/* Strengths */}
      {strengths.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Strengths</p>
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

      {/* Improvements */}
      {improvements.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Improvements</p>
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

// Subset of AnswerEvaluation that EvaluationCard needs — embedded into DisplayMessage
type EvaluationData = {
  relevance_score: number
  depth_score: number
  communication_score: number
  overall_score: number
  strengths: string[]
  improvements: string[]
}

// Local display message — interviewer messages may carry an evaluation to show before the text
type DisplayMessage = {
  role: 'interviewer' | 'candidate'
  content: string
  evaluation?: EvaluationData
}

/** Build a DisplayMessage list from a parsed session, embedding evaluations into the
 *  interviewer turn that follows each candidate answer. */
function toDisplayMessages(session: SessionData): DisplayMessage[] {
  const history = session.conversation_history ?? []
  const answers = session.answers ?? []
  let candidateCount = 0
  return history.map((t) => {
    if (t.role === 'candidate') {
      candidateCount++
      return { role: 'candidate' as const, content: t.content }
    }
    // Attach the evaluation for the most-recent candidate answer (if any)
    const evalIdx = candidateCount - 1
    const ev = evalIdx >= 0 ? answers[evalIdx] : undefined
    return {
      role: 'interviewer' as const,
      content: t.content,
      evaluation: ev
        ? {
            relevance_score:    ev.relevance_score,
            depth_score:        ev.depth_score,
            communication_score: ev.communication_score,
            overall_score:      ev.overall_score,
            strengths:          ev.strengths    ?? [],
            improvements:       ev.improvements ?? [],
          }
        : undefined,
    }
  })
}

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>()   // UUID string from the URL
  const navigate = useNavigate()

  // id IS the UUID session_id — no numeric conversion
  const { data: entity, isPending: loadingSession, isError } = useGetInterview(id ?? null)

  // sessionData holds metadata (questions, answers, status, etc.)
  const [sessionData, setSessionData] = useState<SessionData | null>(null)

  // displayMessages is the source of truth for the chat UI.
  // It is synced from conversation_history on load, then updated optimistically
  // on submit and replaced with the API response when it arrives.
  const [displayMessages,      setDisplayMessages]      = useState<DisplayMessage[]>([])
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false)

  // Track whether this is the first time we've loaded the session (to animate the greeting)
  const initialLoadDone = useRef(false)

  // Sync both sessionData and displayMessages when the entity loads or refreshes
  useEffect(() => {
    if (entity?.agent_state) {
      const parsed = parseSession(entity.agent_state)
      if (parsed) {
        setSessionData(parsed)
        const msgs = toDisplayMessages(parsed)
        setDisplayMessages(msgs)
        // Animate last interviewer message only on the initial page load
        if (!initialLoadDone.current) {
          initialLoadDone.current = true
          const last = msgs[msgs.length - 1]
          if (last?.role === 'interviewer') {
            setIsTyping(true)
          }
        }
      }
    }
  }, [entity])

  // UUID for mutations is the URL param itself
  const sessionUUID = id ?? ''

  const answerMutation = useAnswerInterview(sessionUUID)
  const endMutation    = useEndInterview(sessionUUID)

  const [answer,        setAnswer]        = useState('')
  const [showEndDialog, setShowEndDialog] = useState(false)
  // True while the latest interviewer message is still typewriting
  const [isTyping,      setIsTyping]      = useState(false)
  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const MAX_CHARS = 2000

  // Auto-scroll whenever a new message is appended or the typing indicator appears
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [displayMessages.length, isWaitingForResponse])

  // Sync session metadata and, when called from an answer submission, append new turns
  // to displayMessages without touching the existing history (append-only).
  //
  // fromAnswer = true  → one optimistic candidate message was appended before the call;
  //                       slice it off and replace with real turns from the API response.
  // fromAnswer = false → end-session call; no optimistic message; just update sessionData.
  function handleMutationSuccess(updated: Record<string, unknown>, fromAnswer = false) {
    const parsed = parseSession(updated)
    if (!parsed) {
      setIsWaitingForResponse(false)
      return
    }

    setSessionData(parsed)

    if (fromAnswer) {
      const newHistory = parsed.conversation_history ?? []
      // The Python /answer response returns `evaluation` at the top level (not in an `answers`
      // array). Extract it here to attach to the new interviewer turn in the display.
      const turnEval = updated.evaluation as Record<string, unknown> | undefined

      setDisplayMessages((prev) => {
        // prev ends with the one optimistic candidate message we appended during submit.
        // Everything before that is stable and must not change.
        const preOptimisticCount = Math.max(0, prev.length - 1)
        const kept = prev.slice(0, preOptimisticCount)

        // Turns incoming from the API that we don't yet have displayed
        const incoming = newHistory.slice(preOptimisticCount)

        // Attach the evaluation from this turn to the first new interviewer message only
        let evaluationAttached = false
        const appended: DisplayMessage[] = incoming.map((turn) => {
          if (turn.role === 'candidate') {
            return { role: 'candidate' as const, content: turn.content }
          }
          const ev = !evaluationAttached ? turnEval : undefined
          evaluationAttached = true
          return {
            role: 'interviewer' as const,
            content: turn.content,
            evaluation: ev
              ? {
                  relevance_score:     Number(ev.relevance_score)     || 0,
                  depth_score:         Number(ev.depth_score)         || 0,
                  communication_score: Number(ev.communication_score) || 0,
                  overall_score:       Number(ev.overall_score)       || 0,
                  strengths:           (ev.strengths    as string[])  ?? [],
                  improvements:        (ev.improvements as string[])  ?? [],
                }
              : undefined,
          }
        })

        return [...kept, ...appended]
      })

      // Start typewriter if the last new turn is an interviewer message
      const lastNew = newHistory[newHistory.length - 1]
      if (lastNew?.role === 'interviewer') {
        setIsTyping(true)
      }
    }

    setIsWaitingForResponse(false)
  }

  function handleSubmit() {
    if (!answer.trim() || isWaitingForResponse) return
    const text = answer.trim()
    setAnswer('')

    // Optimistic update: show candidate message immediately and display typing indicator
    setDisplayMessages((prev) => [...prev, { role: 'candidate', content: text }])
    setIsWaitingForResponse(true)

    answerMutation.mutate(
      { answer: text },
      {
        onSuccess: (data) => handleMutationSuccess(data, true),
        onError: () => {
          // Revert the optimistic message so the user can retry
          setIsWaitingForResponse(false)
          setDisplayMessages((prev) => prev.slice(0, -1))
        },
      }
    )
  }

  function handleEnd() {
    setShowEndDialog(true)
  }

  function confirmEnd() {
    setShowEndDialog(false)
    endMutation.mutate(undefined, {
      onSuccess: (data) => {
        handleMutationSuccess(data, false)
        // Pass the full end response to ReviewPage so it doesn't need a separate GET fetch
        navigate(`/review/${id}`, { state: { endData: data } })
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

  // Destructure with fallbacks — every field can be undefined on a partial response
  const questions            = sessionData.questions            ?? []
  const answers              = sessionData.answers              ?? []
  const conversation_history = sessionData.conversation_history ?? []
  const current_question_index = sessionData.current_question_index ?? 0
  const status               = sessionData.status               ?? ''
  const jd_title             = sessionData.jd_title             ?? ''

  const isCompleted = status === 'completed'
  const currentQ    = questions.length > 0
                        ? questions[Math.min(current_question_index, questions.length - 1)]
                        : undefined
  const totalQ      = questions.length
  const answeredQ   = answers.length

  // Index of the latest interviewer message — only that one gets typewriter animation
  const latestInterviewerIdx = displayMessages.reduce(
    (last, t, i) => (t.role === 'interviewer' ? i : last), -1
  )

  // Input is locked while waiting for server response OR while typewriter is animating
  const inputLocked = isWaitingForResponse || isTyping

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
        {displayMessages.map((turn, idx) => {
          const isLatestInterviewer = turn.role === 'interviewer' && idx === latestInterviewerIdx

          return (
            <div key={idx}>
              {/* Evaluation card (scores + feedback) shown BEFORE the interviewer question */}
              {turn.role === 'interviewer' && turn.evaluation && (
                <EvaluationCard eval={turn.evaluation} />
              )}

              {isLatestInterviewer ? (
                // Latest interviewer message: typewriter animation
                <div className="flex items-end gap-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-200 text-gray-500">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
                  </div>
                  <div className="max-w-[75%]">
                    <div className="rounded-2xl rounded-bl-none bg-gray-100 px-4 py-3 text-sm leading-relaxed text-gray-800">
                      <TypewriterText
                        text={turn.content}
                        speed={20}
                        onComplete={() => {
                          setIsTyping(false)
                          setTimeout(() => textareaRef.current?.focus(), 0)
                        }}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <ChatBubble role={turn.role} content={turn.content} />
              )}
            </div>
          )
        })}

        {/* Typing indicator — shown immediately after the candidate message is appended */}
        {isWaitingForResponse && <TypingIndicator />}

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
            ref={textareaRef}
            value={answer}
            onChange={(e) => setAnswer(e.target.value.slice(0, MAX_CHARS))}
            placeholder="Type your answer here…"
            rows={4}
            disabled={inputLocked}
            onKeyDown={(e) => {
              // Enter submits; Shift+Enter inserts a newline as usual
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit()
              }
            }}
            className="w-full resize-none rounded-xl border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-60"
          />

          <div className="flex items-center justify-between">
            <span className={`text-xs ${answer.length >= MAX_CHARS * 0.9 ? 'text-red-500' : 'text-gray-400'}`}>
              {answer.length}/{MAX_CHARS}
            </span>
            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-gray-400 sm:block">Shift+Enter for newline</span>
              <button
                onClick={handleSubmit}
                disabled={!answer.trim() || inputLocked}
                className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isWaitingForResponse ? (
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
