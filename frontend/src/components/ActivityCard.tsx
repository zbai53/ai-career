import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

interface ActivityCardProps {
  title: string
  subtitle?: string
  score?: number
  status?: string
  link: string
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-green-600 bg-green-50'
  if (score >= 50) return 'text-yellow-600 bg-yellow-50'
  return 'text-red-600 bg-red-50'
}

function statusColor(status: string): string {
  const s = status.toLowerCase()
  if (s === 'completed' || s === 'done') return 'text-green-600 bg-green-50'
  if (s === 'in_progress' || s === 'active') return 'text-blue-600 bg-blue-50'
  return 'text-gray-500 bg-gray-100'
}

export default function ActivityCard({ title, subtitle, score, status, link }: ActivityCardProps) {
  return (
    <Link
      to={link}
      className="group flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 transition-colors hover:border-indigo-300 hover:bg-indigo-50/40"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900 group-hover:text-indigo-700">
          {title}
        </p>
        {subtitle && (
          <p className="truncate text-xs text-gray-500 mt-0.5">{subtitle}</p>
        )}
      </div>

      <div className="ml-3 flex shrink-0 items-center gap-2">
        {score !== undefined && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${scoreColor(score)}`}>
            {score}%
          </span>
        )}
        {status !== undefined && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColor(status)}`}>
            {status.replace('_', ' ')}
          </span>
        )}
        <ArrowRight className="h-3.5 w-3.5 text-gray-400 group-hover:text-indigo-500 transition-colors" />
      </div>
    </Link>
  )
}
