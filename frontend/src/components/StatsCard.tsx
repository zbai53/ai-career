import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export interface StatsCardProps {
  icon: React.ElementType
  label: string
  value: string | number
  /** Optional colour classes for the icon pill, e.g. "text-indigo-600 bg-indigo-50" */
  color?: string
  /** Show a directional trend indicator next to the value */
  trend?: 'up' | 'down' | 'neutral'
  /** Whether to show a skeleton pulse (data still loading) */
  loading?: boolean
}

function TrendBadge({ trend }: { trend: 'up' | 'down' | 'neutral' }) {
  if (trend === 'up') {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-green-50 px-1.5 py-0.5 text-[10px] font-semibold text-green-600">
        <TrendingUp className="h-3 w-3" />
        up
      </span>
    )
  }
  if (trend === 'down') {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-500">
        <TrendingDown className="h-3 w-3" />
        down
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
      <Minus className="h-3 w-3" />
    </span>
  )
}

export default function StatsCard({
  icon: Icon,
  label,
  value,
  color = 'text-indigo-600 bg-indigo-50',
  trend,
  loading = false,
}: StatsCardProps) {
  if (loading) {
    return (
      <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-4">
        <div className="mb-3 h-8 w-8 rounded-lg bg-gray-200" />
        <div className="h-7 w-16 rounded bg-gray-200" />
        <div className="mt-1.5 h-3 w-24 rounded bg-gray-100" />
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm">
      <div className={`mb-3 inline-flex rounded-lg p-2 ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex items-end gap-2">
        <p className="text-2xl font-bold tabular-nums text-gray-900 leading-none">{value}</p>
        {trend && <div className="mb-0.5"><TrendBadge trend={trend} /></div>}
      </div>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
    </div>
  )
}
