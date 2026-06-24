import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'

interface FidelityBadgeProps {
  score: number | null
  passed: boolean
}

type Tier = 'verified' | 'warning' | 'failed'

function getTier(score: number | null, passed: boolean): Tier {
  if (!passed || score === null || score < 0.80) return 'failed'
  if (score < 0.90) return 'warning'
  return 'verified'
}

const TIER_CONFIG = {
  verified: {
    label: 'VERIFIED',
    Icon: ShieldCheck,
    classes: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    iconClass: 'text-green-600',
  },
  warning: {
    label: 'WARNING',
    Icon: ShieldAlert,
    classes: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
    iconClass: 'text-yellow-600',
  },
  failed: {
    label: 'FAILED',
    Icon: ShieldX,
    classes: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    iconClass: 'text-red-600',
  },
}

export default function FidelityBadge({ score, passed }: FidelityBadgeProps) {
  const tier = getTier(score, passed)
  const { label, Icon, classes, iconClass } = TIER_CONFIG[tier]

  return (
    <div className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 ${classes}`}>
      <Icon className={`h-4 w-4 shrink-0 ${iconClass}`} />
      <div className="flex items-baseline gap-1.5">
        <span className="text-xs font-bold tracking-wider">{label}</span>
        {score !== null && (
          <span className="text-xs font-medium opacity-75">
            {(score * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  )
}
