import {
  Radar,
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

interface RadarChartProps {
  skillScore: number
  experienceScore: number
  keywordScore: number
  overallScore: number
}

function scoreColor(score: number): string {
  if (score >= 70) return '#16a34a'   // green-600
  if (score >= 50) return '#ca8a04'   // yellow-600
  return '#dc2626'                    // red-600
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'Strong Match'
  if (score >= 50) return 'Partial Match'
  return 'Weak Match'
}

export default function RadarChart({
  skillScore,
  experienceScore,
  keywordScore,
  overallScore,
}: RadarChartProps) {
  const data = [
    { dimension: 'Skills',      score: Math.round(skillScore) },
    { dimension: 'Experience',  score: Math.round(experienceScore) },
    { dimension: 'Keywords',    score: Math.round(keywordScore) },
  ]

  const color = scoreColor(overallScore)

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-8">
      {/* Radar */}
      <div className="w-full max-w-xs shrink-0 h-44 sm:h-56">
        <ResponsiveContainer width="100%" height="100%">
          <RechartsRadar data={data} outerRadius="70%">
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fontSize: 11, fill: '#6b7280' }}
            />
            <Tooltip
              formatter={(value: number) => [`${value}`, 'Score']}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Radar
              dataKey="score"
              stroke={color}
              fill={color}
              fillOpacity={0.2}
              strokeWidth={2}
              dot={{ r: 3, fill: color }}
            />
          </RechartsRadar>
        </ResponsiveContainer>
      </div>

      {/* Overall score */}
      <div className="flex flex-col items-center gap-1">
        <span
          className="text-6xl font-extrabold leading-none tabular-nums"
          style={{ color }}
        >
          {Math.round(overallScore)}
        </span>
        <span className="text-sm font-medium text-gray-500">/ 100</span>
        <span
          className="mt-1 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ backgroundColor: `${color}1a`, color }}
        >
          {scoreLabel(overallScore)}
        </span>
      </div>
    </div>
  )
}
