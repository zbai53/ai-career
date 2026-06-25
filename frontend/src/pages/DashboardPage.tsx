import { useNavigate } from 'react-router-dom'
import {
  FileUp, ClipboardList, Mic, BarChart2, FileText, Users, TrendingUp,
} from 'lucide-react'
import ActivityCard from '../components/ActivityCard'
import StatsCard from '../components/StatsCard'
import WorkflowVisualization from '../components/WorkflowVisualization'
import { useAuthStore } from '../stores/authStore'
import { useWorkflowStore } from '../stores/workflowStore'
import {
  useRecentResumes,
  useRecentMatches,
  useRecentInterviews,
} from '../api/hooks'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso?: string): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(iso))
  } catch {
    return '—'
  }
}

function avgScore(scores: number[]): string {
  if (scores.length === 0) return '—'
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length
  return `${Math.round(avg)}`
}

// ---------------------------------------------------------------------------
// Quick action card
// ---------------------------------------------------------------------------

interface ActionCardProps {
  icon: React.ElementType
  title: string
  description: string
  onClick: () => void
  disabled?: boolean
}

function ActionCard({ icon: Icon, title, description, onClick, disabled }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`group flex flex-col items-start gap-3 rounded-xl border p-5 text-left transition-all
        ${disabled
          ? 'cursor-not-allowed border-gray-200 bg-gray-50 opacity-50'
          : 'cursor-pointer border-gray-200 bg-white hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5'
        }`}
    >
      <div className={`rounded-lg p-2.5 transition-colors ${disabled ? 'bg-gray-100 text-gray-400' : 'bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100'}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className={`text-sm font-semibold ${disabled ? 'text-gray-400' : 'text-gray-900'}`}>{title}</p>
        <p className="mt-0.5 text-xs text-gray-500">{description}</p>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">{title}</h2>
      {children}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Empty activity state (inline, not full-page)
// ---------------------------------------------------------------------------

function InlineEmpty({ message, actionLabel, onAction }: {
  message: string
  actionLabel: string
  onAction: () => void
}) {
  return (
    <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-4 py-8 text-center">
      <p className="text-sm text-gray-500">{message}</p>
      <button
        onClick={onAction}
        className="mt-3 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 transition-colors"
      >
        {actionLabel}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { currentResumeId, currentJDId, currentMatchId, currentInterviewId } = useWorkflowStore()

  const { data: recentResumes,    isLoading: loadingResumes    } = useRecentResumes()
  const { data: recentMatches,    isLoading: loadingMatches    } = useRecentMatches()
  const { data: recentInterviews, isLoading: loadingInterviews } = useRecentInterviews()

  const hasResumeAndJD = currentResumeId !== null && currentJDId !== null

  // Workflow step progress
  const completedSteps = [
    currentResumeId    ? 'upload'    : null,
    currentJDId        ? 'jd'        : null,
    currentMatchId     ? 'match'     : null,
    currentInterviewId ? 'interview' : null,
  ].filter((s): s is string => s !== null)

  // Derived stats from real data (or workflowStore as fallback)
  const resumeCount     = recentResumes?.length    ?? (currentResumeId    ? 1 : 0)
  const interviewsDone  = recentInterviews?.filter((i) => i.status === 'completed').length
                          ?? (currentInterviewId ? 1 : 0)
  const matchScores     = recentMatches?.map((m) => m.overallScore) ?? []
  const avgMatchScore   = matchScores.length > 0 ? avgScore(matchScores) : (currentMatchId ? '—' : '—')

  // Infer JD count from matches (1 JD per match minimum)
  const jdCount = recentMatches?.length ?? (currentJDId ? 1 : 0)

  const firstName = user?.name ?? 'there'

  return (
    <div className="mx-auto max-w-4xl space-y-10">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, <span className="text-indigo-600">{firstName}</span>
        </h1>
        <p className="mt-1 text-gray-500">
          Your AI-powered job search assistant — match, rewrite, and practise.
        </p>
      </div>

      {/* Stats */}
      <Section title="Overview">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatsCard
            icon={FileText}
            label="Resumes Parsed"
            value={resumeCount}
            color="text-indigo-600 bg-indigo-50"
            loading={loadingResumes}
          />
          <StatsCard
            icon={ClipboardList}
            label="JDs Analyzed"
            value={jdCount}
            color="text-purple-600 bg-purple-50"
            loading={loadingMatches}
          />
          <StatsCard
            icon={Users}
            label="Interviews Done"
            value={interviewsDone}
            color="text-green-600 bg-green-50"
            loading={loadingInterviews}
          />
          <StatsCard
            icon={TrendingUp}
            label="Avg Match Score"
            value={avgMatchScore}
            color="text-amber-600 bg-amber-50"
            loading={loadingMatches}
            trend={
              matchScores.length === 0
                ? undefined
                : Number(avgMatchScore) >= 70 ? 'up'
                : Number(avgMatchScore) >= 50 ? 'neutral'
                : 'down'
            }
          />
        </div>
      </Section>

      {/* Quick actions */}
      <Section title="Quick Actions">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ActionCard
            icon={FileUp}
            title="Upload Resume"
            description="Parse a PDF or DOCX resume with AI"
            onClick={() => navigate('/upload')}
          />
          <ActionCard
            icon={ClipboardList}
            title="Input Job Description"
            description="Paste or fetch a JD to analyse"
            onClick={() => navigate('/jd')}
          />
          <ActionCard
            icon={Mic}
            title="Start Interview"
            description={hasResumeAndJD ? 'Practice with an AI interviewer' : 'Upload resume and JD first'}
            onClick={() => navigate('/jd')}
            disabled={!hasResumeAndJD}
          />
        </div>
      </Section>

      {/* Workflow Progress */}
      <Section title="Workflow Progress">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" style={{ height: 360 }}>
          <WorkflowVisualization completedSteps={completedSteps} />
        </div>
      </Section>

      {/* Recent activity */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Recent matches */}
        <Section title="Recent Matches">
          {loadingMatches ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-100" />
              ))}
            </div>
          ) : (recentMatches ?? []).length > 0 ? (
            <div className="space-y-2">
              {recentMatches!.map((m) => (
                <ActivityCard
                  key={m.id}
                  title={`Match #${m.id}`}
                  subtitle={formatDate(m.createdAt)}
                  score={Math.round(m.overallScore)}
                  link={`/match/${m.id}`}
                />
              ))}
              <button
                onClick={() => navigate('/jd')}
                className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-gray-300 py-2.5 text-xs font-medium text-gray-500 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
              >
                <BarChart2 className="h-3.5 w-3.5" />
                Run a new match
              </button>
            </div>
          ) : (
            <InlineEmpty
              message="No match results yet."
              actionLabel="Run a match"
              onAction={() => navigate('/jd')}
            />
          )}
        </Section>

        {/* Recent interviews */}
        <Section title="Recent Interviews">
          {loadingInterviews ? (
            <div className="space-y-2">
              {[0, 1].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-100" />
              ))}
            </div>
          ) : (recentInterviews ?? []).length > 0 ? (
            <div className="space-y-2">
              {recentInterviews!.map((iv) => (
                <ActivityCard
                  key={iv.id}
                  title={`Interview #${iv.id}`}
                  subtitle={[
                    formatDate(iv.createdAt),
                    iv.questionCount ? `${iv.questionCount}Q` : null,
                  ].filter(Boolean).join(' · ')}
                  status={iv.status}
                  link={iv.status === 'completed' ? `/review/${iv.sessionId}` : `/interview/${iv.sessionId}`}
                />
              ))}
              <button
                onClick={() => navigate('/jd')}
                className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-gray-300 py-2.5 text-xs font-medium text-gray-500 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
              >
                <Mic className="h-3.5 w-3.5" />
                Start a new interview
              </button>
            </div>
          ) : (
            <InlineEmpty
              message="No interviews yet."
              actionLabel="Start an interview"
              onAction={() => navigate('/jd')}
            />
          )}
        </Section>
      </div>
    </div>
  )
}
