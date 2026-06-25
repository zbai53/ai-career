import { useNavigate } from 'react-router-dom'
import { FileUp, ClipboardList, Mic, BarChart2, FileText, Users, TrendingUp } from 'lucide-react'
import ActivityCard from '../components/ActivityCard'
import WorkflowVisualization from '../components/WorkflowVisualization'
import { useAuthStore } from '../stores/authStore'
import { useWorkflowStore } from '../stores/workflowStore'

// ---------------------------------------------------------------------------
// Placeholder data — will connect to real API in a later day
// ---------------------------------------------------------------------------

const PLACEHOLDER_STATS = [
  { label: 'Resumes Parsed',      value: '—',   icon: FileText,  color: 'text-indigo-600 bg-indigo-50' },
  { label: 'JDs Analyzed',        value: '—',   icon: ClipboardList, color: 'text-purple-600 bg-purple-50' },
  { label: 'Interviews Completed',value: '—',   icon: Users,     color: 'text-green-600  bg-green-50'  },
  { label: 'Avg Match Score',     value: '—',   icon: TrendingUp, color: 'text-amber-600  bg-amber-50'  },
]

const PLACEHOLDER_MATCHES = [
  { title: 'Software Engineer @ Stripe',      subtitle: '—',          score: undefined, link: '/match/latest' },
  { title: 'Backend Engineer @ Shopify',      subtitle: '—',          score: undefined, link: '/match/latest' },
  { title: 'Senior SWE @ Anthropic',          subtitle: '—',          score: undefined, link: '/match/latest' },
]

const PLACEHOLDER_INTERVIEWS = [
  { title: 'Software Engineer @ Stripe',   subtitle: '—', status: 'pending', link: '/interview/latest' },
  { title: 'Backend Engineer @ Shopify',   subtitle: '—', status: 'pending', link: '/interview/latest' },
]

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
        <p className={`text-sm font-semibold ${disabled ? 'text-gray-400' : 'text-gray-900'}`}>
          {title}
        </p>
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
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { currentResumeId, currentJDId, currentMatchId, currentInterviewId } = useWorkflowStore()

  const hasResumeAndJD = currentResumeId !== null && currentJDId !== null

  const completedSteps = [
    currentResumeId    ? 'upload'    : null,
    currentJDId        ? 'jd'        : null,
    currentMatchId     ? 'match'     : null,
    currentInterviewId ? 'interview' : null,
  ].filter((s): s is string => s !== null)
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
          {PLACEHOLDER_STATS.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className={`mb-3 inline-flex rounded-lg p-2 ${color}`}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="text-2xl font-bold text-gray-900">{value}</p>
              <p className="mt-0.5 text-xs text-gray-500">{label}</p>
            </div>
          ))}
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
            description={
              hasResumeAndJD
                ? 'Practice with an AI interviewer'
                : 'Upload resume and JD first'
            }
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
          <div className="space-y-2">
            {PLACEHOLDER_MATCHES.map((item) => (
              <ActivityCard
                key={item.title}
                title={item.title}
                subtitle={item.subtitle}
                score={item.score}
                link={item.link}
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
        </Section>

        {/* Recent interviews */}
        <Section title="Recent Interviews">
          <div className="space-y-2">
            {PLACEHOLDER_INTERVIEWS.map((item) => (
              <ActivityCard
                key={item.title}
                title={item.title}
                subtitle={item.subtitle}
                status={item.status}
                link={item.link}
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
        </Section>
      </div>
    </div>
  )
}
