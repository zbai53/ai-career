import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
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

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload Resume', icon: FileUp },
  { to: '/jd', label: 'Input JD', icon: ClipboardList },
  { to: '/match/latest', label: 'Match Results', icon: BarChart2 },
  { to: '/rewrite/latest', label: 'Resume Rewrite', icon: FileText },
  { to: '/interview/latest', label: 'Mock Interview', icon: MessageSquare },
  { to: '/review/latest', label: 'Interview Review', icon: Star },
]

const linkBase =
  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors'
const linkActive = 'bg-indigo-50 text-indigo-700'
const linkInactive = 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 px-4 border-b border-gray-200">
        <BriefcaseBusiness className="h-6 w-6 text-indigo-600" />
        <span className="text-lg font-bold text-gray-900">AI Career</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `${linkBase} ${isActive ? linkActive : linkInactive}`
            }
            onClick={() => setSidebarOpen(false)}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-gray-200 bg-white md:flex">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-gray-200 bg-white transition-transform md:hidden ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <SidebarContent />
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-4 md:px-6">
          {/* Hamburger — mobile only */}
          <button
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 md:hidden"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          {/* Mobile logo (shown when sidebar is hidden) */}
          <div className="flex items-center gap-2 md:hidden">
            <BriefcaseBusiness className="h-5 w-5 text-indigo-600" />
            <span className="font-bold text-gray-900">AI Career</span>
          </div>

          <div className="flex-1" />

          {/* User avatar placeholder */}
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white">
            U
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
