import { useNavigate } from 'react-router-dom'
import {
  FileUp, ClipboardList, BarChart2, FileEdit, MessageSquare, Trophy,
  CheckCircle2, ChevronRight, GitBranch,
} from 'lucide-react'
import WorkflowVisualization from '../components/WorkflowVisualization'
import EmptyState from '../components/EmptyState'
import { useWorkflowStore } from '../stores/workflowStore'

const STEP_INFO: Record<string, { label: string; description: string; link: string; icon: React.ElementType }> = {
  upload:    { label: 'Resume Uploaded',        description: 'Your resume has been parsed and stored.',            link: '/upload',           icon: FileUp        },
  jd:        { label: 'Job Description Parsed', description: 'The job description has been analyzed.',             link: '/jd',               icon: ClipboardList },
  match:     { label: 'Match Analysis Run',     description: 'Your resume was scored against the JD.',            link: '/match/latest',     icon: BarChart2     },
  rewrite:   { label: 'Resume Rewritten',       description: 'Your resume was optimized for the role.',           link: '/rewrite/latest',   icon: FileEdit      },
  interview: { label: 'Interview Practiced',    description: 'You completed a mock interview session.',           link: '/interview/latest', icon: MessageSquare },
  coach:     { label: 'Coach Review Generated', description: 'Your interview performance has been reviewed.',     link: '/review/latest',    icon: Trophy        },
}

const STEP_ORDER = ['upload', 'jd', 'match', 'rewrite', 'interview', 'coach']

export default function WorkflowPage() {
  const navigate = useNavigate()
  const { currentResumeId, currentJDId, currentMatchId, currentInterviewId } = useWorkflowStore()

  const completedSteps = [
    currentResumeId    ? 'upload'    : null,
    currentJDId        ? 'jd'        : null,
    currentMatchId     ? 'match'     : null,
    currentInterviewId ? 'interview' : null,
  ].filter((s): s is string => s !== null)

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Workflow</h1>
        <p className="mt-1 text-sm text-gray-500">
          Your AI career pipeline — from resume to interview readiness.
        </p>
      </div>

      {/* Graph */}
      <div
        className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm"
        style={{ height: 500 }}
      >
        <WorkflowVisualization
          completedSteps={completedSteps}
          showControls
          interactive
        />
      </div>

      {/* Timeline */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Progress ({completedSteps.length}/{STEP_ORDER.length} steps)
        </h2>

        {completedSteps.length === 0 ? (
          <EmptyState
            icon={<GitBranch className="h-8 w-8" />}
            title="No steps completed yet"
            description="Upload your resume to get started with the AI career workflow."
            actionLabel="Upload Resume"
            onAction={() => navigate('/upload')}
          />
        ) : (
          <div className="space-y-2">
            {STEP_ORDER.filter((s) => completedSteps.includes(s)).map((stepId) => {
              const { label, description, link, icon: Icon } = STEP_INFO[stepId]
              return (
                <button
                  key={stepId}
                  onClick={() => navigate(link)}
                  className="flex w-full items-center gap-4 rounded-xl border border-gray-200 bg-white px-4 py-3 text-left hover:border-indigo-300 hover:bg-indigo-50/40 transition-colors"
                >
                  <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100">
                    <Icon className="h-4 w-4 text-gray-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{label}</p>
                    <p className="text-xs text-gray-500">{description}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-gray-400" />
                </button>
              )
            })}
          </div>
        )}
      </section>

      {/* Next step prompt */}
      {completedSteps.length < STEP_ORDER.length && (() => {
        const nextStep = STEP_ORDER.find((s) => !completedSteps.includes(s))
        if (!nextStep) return null
        const { label, link, icon: Icon } = STEP_INFO[nextStep]
        return (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Next Step</h2>
            <button
              onClick={() => navigate(link)}
              className="flex w-full items-center gap-4 rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50 px-4 py-4 text-left hover:bg-indigo-100 transition-colors"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600">
                <Icon className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-indigo-800">{label}</p>
                <p className="text-xs text-indigo-600">Click to continue →</p>
              </div>
            </button>
          </section>
        )
      })()}
    </div>
  )
}
