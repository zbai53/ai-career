import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import ToastContainer from './ToastContainer'
import {
  LayoutDashboard,
  FileUp,
  ClipboardList,
  BarChart2,
  FileText,
  MessageSquare,
  Star,
  Menu,
  X,
  BriefcaseBusiness,
  GitBranch,
  CheckCircle2,
  Circle,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useWorkflowStore } from '../stores/workflowStore'

// Each nav item can have an optional "step" field that maps to a workflow completed state
interface NavItem {
  to: string
  label: string
  icon: React.ElementType
  end: boolean
  step?: 'resume' | 'jd' | 'match' | 'interview'
}

const navItems: NavItem[] = [
  { to: '/',               label: 'Dashboard',       icon: LayoutDashboard, end: true                 },
  { to: '/upload',         label: 'Upload Resume',    icon: FileUp,          end: false, step: 'resume'    },
  { to: '/jd',             label: 'Input JD',         icon: ClipboardList,   end: false, step: 'jd'        },
  { to: '/match/latest',   label: 'Match Results',    icon: BarChart2,       end: false, step: 'match'     },
  { to: '/rewrite/latest', label: 'Resume Rewrite',   icon: FileText,        end: false                },
  { to: '/interview/latest', label: 'Mock Interview', icon: MessageSquare,   end: false, step: 'interview' },
  { to: '/review/latest',  label: 'Interview Review', icon: Star,            end: false                },
  { to: '/workflow',       label: 'Workflow',         icon: GitBranch,       end: false                },
]

// Bottom tab items for mobile (5 most important)
const mobileTabItems: NavItem[] = [
  { to: '/',               label: 'Home',      icon: LayoutDashboard, end: true  },
  { to: '/upload',         label: 'Upload',    icon: FileUp,          end: false, step: 'resume' },
  { to: '/match/latest',   label: 'Match',     icon: BarChart2,       end: false, step: 'match'  },
  { to: '/interview/latest', label: 'Interview', icon: MessageSquare, end: false, step: 'interview' },
  { to: '/workflow',       label: 'Workflow',  icon: GitBranch,       end: false },
]

const PAGE_TITLE_MAP: [RegExp, string][] = [
  [/^\/$/, 'Dashboard'],
  [/^\/upload/, 'Upload Resume'],
  [/^\/jd/, 'Input Job Description'],
  [/^\/match/, 'Match Results'],
  [/^\/rewrite/, 'Resume Rewrite'],
  [/^\/interview/, 'Mock Interview'],
  [/^\/review/, 'Interview Review'],
  [/^\/workflow/, 'Workflow'],
]

function getPageTitle(pathname: string): string {
  for (const [pattern, title] of PAGE_TITLE_MAP) {
    if (pattern.test(pathname)) return title
  }
  return 'AI Career'
}

interface StepStatus {
  resume: boolean
  jd: boolean
  match: boolean
  interview: boolean
}

function SidebarNav({ onNavigate, stepStatus }: { onNavigate?: () => void; stepStatus: StepStatus }) {
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
      {navItems.map(({ to, label, icon: Icon, end, step }) => {
        const isDone = step ? stepStatus[step] : false
        return (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700 shadow-sm'
                  : 'text-gray-600 hover:bg-white/80 hover:text-gray-900 hover:shadow-sm'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-indigo-600" />
                )}
                <Icon
                  className={`h-4 w-4 shrink-0 transition-colors ${
                    isActive ? 'text-indigo-600' : 'text-gray-400 group-hover:text-gray-600'
                  }`}
                />
                <span className="flex-1">{label}</span>
                {/* Step completion indicator */}
                {step && (
                  isDone
                    ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                    : <Circle className="h-3.5 w-3.5 text-gray-200 shrink-0" />
                )}
              </>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

// Compute overall progress percentage
function computeProgress(status: StepStatus): number {
  const steps = [status.resume, status.jd, status.match, status.interview]
  const done = steps.filter(Boolean).length
  return Math.round((done / steps.length) * 100)
}

function SidebarShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-slate-50 via-white to-indigo-50/20">
      {children}
    </div>
  )
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const { currentResumeId, currentJDId, currentMatchId, currentInterviewId } = useWorkflowStore()

  const stepStatus: StepStatus = {
    resume: currentResumeId !== null,
    jd: currentJDId !== null,
    match: currentMatchId !== null,
    interview: currentInterviewId !== null,
  }
  const progress = computeProgress(stepStatus)

  const pageTitle = getPageTitle(location.pathname)
  const initials = user?.name ? user.name.slice(0, 2).toUpperCase() : 'U'

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ── Desktop sidebar ──────────────────────────────────────────────── */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-gray-200/80 shadow-sm md:flex">
        <SidebarShell>
          {/* Logo */}
          <div className="flex h-16 items-center gap-2.5 border-b border-gray-200/80 px-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 shadow-sm">
              <BriefcaseBusiness className="h-4 w-4 text-white" />
            </div>
            <span className="text-base font-bold text-gray-900">AI Career</span>
          </div>

          {/* Progress bar */}
          {progress > 0 && (
            <div className="px-4 pt-3 pb-1">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                <span className="font-medium">Workflow progress</span>
                <span className="font-semibold text-indigo-600">{progress}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-indigo-600 transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          <SidebarNav stepStatus={stepStatus} />

          {/* Bottom user strip */}
          <div className="border-t border-gray-200/80 p-3 space-y-2">
            <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-gray-100 transition-colors cursor-default">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 text-xs font-bold text-white">
                {initials}
              </div>
              <span className="truncate text-xs font-medium text-gray-600">
                {user?.email ?? 'Guest'}
              </span>
            </div>
            {/* Footer */}
            <div className="px-2 pb-0.5">
              <p className="text-[10px] text-gray-400 leading-relaxed">
                AI Career <span className="text-gray-300">v0.1</span>
              </p>
              <p className="text-[10px] text-gray-400">
                Powered by{' '}
                <span className="font-medium text-indigo-400">Claude</span>
              </p>
            </div>
          </div>
        </SidebarShell>
      </aside>

      {/* ── Mobile sidebar overlay ───────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 backdrop-blur-[1px] md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Mobile sidebar drawer (full menu access) ─────────────────────── */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-60 border-r border-gray-200 shadow-xl transition-transform duration-200 md:hidden ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <SidebarShell>
          <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 shadow-sm">
                <BriefcaseBusiness className="h-4 w-4 text-white" />
              </div>
              <span className="text-base font-bold text-gray-900">AI Career</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="rounded-md p-1 text-gray-400 hover:bg-gray-100">
              <X className="h-4 w-4" />
            </button>
          </div>

          <SidebarNav stepStatus={stepStatus} onNavigate={() => setSidebarOpen(false)} />

          <div className="border-t border-gray-200 p-3">
            <p className="px-2 text-[10px] text-gray-400">AI Career v0.1 · Powered by <span className="font-medium text-indigo-400">Claude</span></p>
          </div>
        </SidebarShell>
      </aside>

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-gray-200 bg-white px-4 shadow-sm md:h-16 md:px-6">
          {/* Hamburger — mobile only */}
          <button
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 md:hidden"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <h1 className="text-sm font-semibold text-gray-800 md:text-base">{pageTitle}</h1>

          <div className="flex-1" />

          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 text-sm font-bold text-white shadow-sm">
            {initials}
          </div>
        </header>

        {/* Page content */}
        <main
          key={location.key}
          className="page-enter flex-1 overflow-y-auto p-4 pb-20 md:p-8 md:pb-8"
        >
          <Outlet />
        </main>

        {/* ── Mobile bottom tab bar ─────────────────────────────────────── */}
        <nav className="fixed bottom-0 left-0 right-0 z-10 flex h-16 items-center justify-around border-t border-gray-200 bg-white/95 backdrop-blur-md md:hidden">
          {mobileTabItems.map(({ to, label, icon: Icon, end, step }) => {
            const isDone = step ? stepStatus[step as keyof StepStatus] : false
            return (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `relative flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg transition-colors ${
                    isActive ? 'text-indigo-600' : 'text-gray-500'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isDone && !isActive && (
                      <span className="absolute top-1 right-2 h-2 w-2 rounded-full bg-green-400 ring-1 ring-white" />
                    )}
                    <Icon className={`h-5 w-5 ${isActive ? 'text-indigo-600' : 'text-gray-500'}`} />
                    <span className={`text-[10px] font-medium ${isActive ? 'text-indigo-600' : 'text-gray-500'}`}>
                      {label}
                    </span>
                    {isActive && (
                      <span className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-6 rounded-full bg-indigo-600" />
                    )}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* Global toast notifications */}
      <ToastContainer />
    </div>
  )
}
