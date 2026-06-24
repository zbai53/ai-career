import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
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
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

const navItems = [
  { to: '/',               label: 'Dashboard',       icon: LayoutDashboard, end: true  },
  { to: '/upload',         label: 'Upload Resume',    icon: FileUp,          end: false },
  { to: '/jd',             label: 'Input JD',         icon: ClipboardList,   end: false },
  { to: '/match/latest',   label: 'Match Results',    icon: BarChart2,       end: false },
  { to: '/rewrite/latest', label: 'Resume Rewrite',   icon: FileText,        end: false },
  { to: '/interview/latest', label: 'Mock Interview', icon: MessageSquare,   end: false },
  { to: '/review/latest',  label: 'Interview Review', icon: Star,            end: false },
]

// Map route prefix → page title shown in the top bar
const PAGE_TITLE_MAP: [RegExp, string][] = [
  [/^\/$/,           'Dashboard'],
  [/^\/upload/,      'Upload Resume'],
  [/^\/jd/,          'Input Job Description'],
  [/^\/match/,       'Match Results'],
  [/^\/rewrite/,     'Resume Rewrite'],
  [/^\/interview/,   'Mock Interview'],
  [/^\/review/,      'Interview Review'],
]

function getPageTitle(pathname: string): string {
  for (const [pattern, title] of PAGE_TITLE_MAP) {
    if (pattern.test(pathname)) return title
  }
  return 'AI Career'
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
      {navItems.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
            }`
          }
        >
          {({ isActive }) => (
            <>
              {/* Active left-bar indicator */}
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-indigo-600" />
              )}
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-indigo-600' : 'text-gray-400 group-hover:text-gray-600'}`} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function SidebarShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-white to-gray-50/80">
      {children}
    </div>
  )
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const user = useAuthStore((s) => s.user)

  const pageTitle = getPageTitle(location.pathname)
  const initials  = user?.name
    ? user.name.slice(0, 2).toUpperCase()
    : 'U'

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ── Desktop sidebar ──────────────────────────────────────────────── */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-gray-200 shadow-sm md:flex">
        <SidebarShell>
          {/* Logo */}
          <div className="flex h-16 items-center gap-2.5 border-b border-gray-200 px-4">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600">
              <BriefcaseBusiness className="h-4 w-4 text-white" />
            </div>
            <span className="text-base font-bold text-gray-900">AI Career</span>
          </div>

          <SidebarNav />

          {/* Bottom user strip */}
          <div className="border-t border-gray-200 p-3">
            <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                {initials}
              </div>
              <span className="truncate text-xs font-medium text-gray-600">
                {user?.email ?? 'Guest'}
              </span>
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

      {/* ── Mobile sidebar drawer ────────────────────────────────────────── */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-60 border-r border-gray-200 shadow-lg transition-transform duration-200 md:hidden ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <SidebarShell>
          <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600">
                <BriefcaseBusiness className="h-4 w-4 text-white" />
              </div>
              <span className="text-base font-bold text-gray-900">AI Career</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="rounded-md p-1 text-gray-400 hover:bg-gray-100">
              <X className="h-4 w-4" />
            </button>
          </div>

          <SidebarNav onNavigate={() => setSidebarOpen(false)} />
        </SidebarShell>
      </aside>

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-4 border-b border-gray-200 bg-white px-4 shadow-sm md:px-6">
          {/* Hamburger — mobile only */}
          <button
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 md:hidden"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Page title */}
          <h1 className="text-base font-semibold text-gray-800">{pageTitle}</h1>

          <div className="flex-1" />

          {/* User avatar */}
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white shadow-sm">
            {initials}
          </div>
        </header>

        {/* Page content — keyed on location to trigger fade-in on navigation */}
        <main
          key={location.key}
          className="page-enter flex-1 overflow-y-auto p-6 md:p-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
