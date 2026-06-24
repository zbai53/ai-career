import { useNavigate } from 'react-router-dom'
import { CheckCircle2, ArrowRight, RefreshCw } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import { useParseResume } from '../api/hooks'
import { useWorkflowStore } from '../stores/workflowStore'

// ---------------------------------------------------------------------------
// Helpers to pull typed fields out of the opaque parsedData blob
// ---------------------------------------------------------------------------

function str(obj: unknown, ...keys: string[]): string {
  let cur: unknown = obj
  for (const k of keys) {
    if (cur == null || typeof cur !== 'object') return ''
    cur = (cur as Record<string, unknown>)[k]
  }
  return typeof cur === 'string' ? cur : ''
}

function arr(obj: unknown, ...keys: string[]): unknown[] {
  let cur: unknown = obj
  for (const k of keys) {
    if (cur == null || typeof cur !== 'object') return []
    cur = (cur as Record<string, unknown>)[k]
  }
  return Array.isArray(cur) ? cur : []
}

function num(obj: unknown, ...keys: string[]): number {
  let cur: unknown = obj
  for (const k of keys) {
    if (cur == null || typeof cur !== 'object') return 0
    cur = (cur as Record<string, unknown>)[k]
  }
  return typeof cur === 'number' ? cur : 0
}

/** Skills can be plain strings OR objects {name, category, proficiency}. */
function skillName(skill: unknown): string {
  if (typeof skill === 'string') return skill
  if (skill && typeof skill === 'object') {
    const s = (skill as Record<string, unknown>).name
    return typeof s === 'string' ? s : ''
  }
  return ''
}

// ---------------------------------------------------------------------------

function SkillBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
      {label}
    </span>
  )
}

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-6 space-y-4">
      <div className="h-5 w-1/3 rounded bg-gray-200" />
      <div className="h-4 w-1/2 rounded bg-gray-200" />
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => <div key={i} className="h-16 rounded-lg bg-gray-100" />)}
      </div>
      <div className="h-3 w-full rounded bg-gray-200" />
      <div className="flex flex-wrap gap-2">
        {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-6 w-16 rounded-full bg-gray-200" />)}
      </div>
    </div>
  )
}

export default function ResumeUploadPage() {
  const navigate = useNavigate()
  const setResumeId = useWorkflowStore((s) => s.setResumeId)

  const { mutate, isPending, isSuccess, isError, error, data, reset } = useParseResume()

  const pd = data?.parsedData ?? {}

  const name       = str(pd, 'contact', 'name')
  const email      = str(pd, 'contact', 'email')
  const education  = arr(pd, 'education')
  const experience = arr(pd, 'experience')
  const skills     = arr(pd, 'skills')
  const confidence = num(pd, 'parse_confidence') * 100  // 0–1 → 0–100

  function handleContinue() {
    if (!data) return
    setResumeId(data.id)
    navigate('/jd')
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Resume</h1>
        <p className="mt-1 text-gray-500">
          Upload your resume in PDF or DOCX format. Our AI will extract structured data from it.
        </p>
      </div>

      {/* Upload area — hidden once we have a result */}
      {!isSuccess && (
        <FileUpload
          onUpload={(file) => mutate(file)}
          isLoading={isPending}
          error={isError ? (error?.message ?? 'Upload failed. Please try again.') : null}
        />
      )}

      {/* Skeleton while parsing */}
      {isPending && <SkeletonCard />}

      {/* Success: parsed summary */}
      {isSuccess && data && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">Resume parsed successfully</span>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-5">
            {/* Contact */}
            <div>
              <p className="text-lg font-semibold text-gray-900">{name || 'Name not detected'}</p>
              {email && <p className="text-sm text-gray-500">{email}</p>}
            </div>

            {/* Counts */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Education', value: education.length },
                { label: 'Experience', value: experience.length },
                { label: 'Skills', value: skills.length },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-lg bg-gray-50 p-4 text-center">
                  <p className="text-2xl font-bold text-indigo-600">{value}</p>
                  <p className="text-xs text-gray-500 mt-1">{label}</p>
                </div>
              ))}
            </div>

            {/* Confidence bar */}
            {confidence > 0 && (
              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Parse confidence</span>
                  <span>{confidence.toFixed(0)}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-100">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      confidence >= 80 ? 'bg-green-500' : confidence >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${confidence}%` }}
                  />
                </div>
              </div>
            )}

            {/* Skills */}
            {skills.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Extracted skills</p>
                <div className="flex flex-wrap gap-2">
                  {skills.slice(0, 20).map((skill, i) => (
                    <SkillBadge key={skillName(skill) || i} label={skillName(skill)} />
                  ))}
                  {skills.length > 20 && (
                    <span className="text-xs text-gray-400 self-center">
                      +{skills.length - 20} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={reset}
              className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              <RefreshCw className="h-4 w-4" />
              Upload different file
            </button>

            <button
              onClick={handleContinue}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Continue to JD Input
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
