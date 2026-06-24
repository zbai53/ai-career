import { CheckCircle2 } from 'lucide-react'

interface BulletComparisonProps {
  original: string
  rewritten: string
  changes: string[]
  /** Keywords that were injected — highlighted in the rewritten text */
  keywordsInjected?: string[]
}

/** Split `text` into alternating [plain, highlighted, plain, ...] segments. */
function highlight(text: string, keywords: string[]): Array<{ text: string; hl: boolean }> {
  if (!keywords.length) return [{ text, hl: false }]

  // Build a single regex with word-boundary awareness, case-insensitive
  const pattern = keywords
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')
  const re = new RegExp(`(${pattern})`, 'gi')

  const parts: Array<{ text: string; hl: boolean }> = []
  let last = 0
  let match: RegExpExecArray | null

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), hl: false })
    parts.push({ text: match[0], hl: true })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last), hl: false })
  return parts
}

export default function BulletComparison({
  original,
  rewritten,
  changes,
  keywordsInjected = [],
}: BulletComparisonProps) {
  const segments = highlight(rewritten, keywordsInjected)

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden text-sm">
      {/* Bullet columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2">
        {/* Original */}
        <div className="bg-gray-50 p-4 sm:border-r sm:border-gray-200">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
            Original
          </p>
          <p className="leading-relaxed text-gray-700">{original}</p>
        </div>

        {/* Rewritten */}
        <div className="bg-green-50 p-4">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-green-600">
            Rewritten
          </p>
          <p className="leading-relaxed text-gray-800">
            {segments.map((seg, i) =>
              seg.hl ? (
                <mark
                  key={i}
                  className="bg-green-200 text-green-900 font-semibold rounded px-0.5 not-italic"
                >
                  {seg.text}
                </mark>
              ) : (
                <span key={i}>{seg.text}</span>
              )
            )}
          </p>
        </div>
      </div>

      {/* Changes made */}
      {changes.length > 0 && (
        <div className="border-t border-gray-200 bg-white px-4 py-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
            Changes made
          </p>
          <ul className="space-y-1">
            {changes.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-500" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
