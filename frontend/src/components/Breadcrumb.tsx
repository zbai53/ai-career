import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'

const ROUTE_LABELS: [RegExp, string][] = [
  [/^\/upload/,    'Upload Resume'],
  [/^\/jd/,        'Input JD'],
  [/^\/match/,     'Match Results'],
  [/^\/rewrite/,   'Resume Rewrite'],
  [/^\/interview/, 'Mock Interview'],
  [/^\/review/,    'Interview Review'],
  [/^\/workflow/,  'Workflow'],
]

interface Crumb { label: string; to: string }

function buildCrumbs(pathname: string): Crumb[] {
  const crumbs: Crumb[] = [{ label: 'Dashboard', to: '/' }]
  for (const [pattern, label] of ROUTE_LABELS) {
    if (pattern.test(pathname)) {
      crumbs.push({ label, to: pathname })
      break
    }
  }
  return crumbs
}

export default function Breadcrumb() {
  const { pathname } = useLocation()
  const crumbs = buildCrumbs(pathname)
  if (crumbs.length <= 1) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-gray-400 mb-1">
      {crumbs.map((crumb, i) => (
        <span key={crumb.to} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3 w-3 text-gray-300" />}
          {i === crumbs.length - 1 ? (
            <span className="font-medium text-gray-500">{crumb.label}</span>
          ) : (
            <Link to={crumb.to} className="flex items-center gap-0.5 hover:text-indigo-600 transition-colors">
              <Home className="h-3 w-3" />
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
