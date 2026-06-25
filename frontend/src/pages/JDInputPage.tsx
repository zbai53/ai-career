import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link2, FileText, Loader2, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { useParseJD, useMatch } from '../api/hooks'
import { useWorkflowStore } from '../stores/workflowStore'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function str(obj: unknown, key: string): string {
  if (obj == null || typeof obj !== 'object') return ''
  const v = (obj as Record<string, unknown>)[key]
  return typeof v === 'string' ? v : ''
}

function arr(obj: unknown, key: string): string[] {
  if (obj == null || typeof obj !== 'object') return []
  const v = (obj as Record<string, unknown>)[key]
  return Array.isArray(v) ? (v as string[]) : []
}

// ---------------------------------------------------------------------------

function Badge({ label, variant }: { label: string; variant: 'red' | 'blue' | 'gray' }) {
  const cls =
    variant === 'red'
      ? 'bg-red-100 text-red-700'
      : variant === 'blue'
      ? 'bg-blue-100 text-blue-700'
      : 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

type InputMode = 'text' | 'url'

export default function JDInputPage() {
  const navigate = useNavigate()
  const { currentResumeId, setJDId, setMatchId } = useWorkflowStore()

  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')

  const parseJD = useParseJD()
  const match   = useMatch()

  const pd = parseJD.data?.parsedData ?? {}

  const title           = str(pd, 'title')
  const company         = str(pd, 'company')
  const location        = str(pd, 'location')
  const remoteType      = str(pd, 'remote_type')
  const requiredSkills  = arr(pd, 'required_skills')
  const preferredSkills = arr(pd, 'preferred_skills')
  const keywords        = arr(pd, 'keywords')

  function handleParse() {
    if (mode === 'text' && text.trim()) {
      parseJD.mutate({ text: text.trim() })
    } else if (mode === 'url' && url.trim()) {
      parseJD.mutate({ url: url.trim() })
    }
  }

  async function handleMatch() {
    if (!parseJD.data || !currentResumeId) return
    const jdId = parseJD.data.id
    setJDId(jdId)
    match.mutate(
      { resumeId: currentResumeId, jdId },
      {
        onSuccess: (result) => {
          setMatchId(result.id)
          navigate(`/match/${result.id}`)
        },
      }
    )
  }

  const canParse = mode === 'text' ? text.trim().length > 0 : url.trim().length > 0
  const noResumeWarning = parseJD.isSuccess && !currentResumeId

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader
        title="Input Job Description"
        subtitle="Paste the full job description or provide a URL. Our AI will extract structured data."
      />

      {/* Input panel */}
      {!parseJD.isSuccess && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          {/* Mode toggle */}
          <div className="flex rounded-lg border border-gray-200 p-1 w-fit gap-1">
            {(['text', 'url'] as InputMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  mode === m
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {m === 'text' ? <FileText className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
                {m === 'text' ? 'Paste text' : 'Enter URL'}
              </button>
            ))}
          </div>

          {/* Input */}
          {mode === 'text' ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the full job description here…"
              rows={12}
              className="w-full resize-y rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          ) : (
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.linkedin.com/jobs/view/…"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          )}

          {/* Error */}
          {parseJD.isError && (
            <p className="flex items-center gap-1.5 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {parseJD.error?.message ?? 'Failed to parse JD. Please try again.'}
            </p>
          )}

          {/* Parse button */}
          <button
            onClick={handleParse}
            disabled={!canParse || parseJD.isPending}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {parseJD.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Parsing…
              </>
            ) : (
              'Parse Job Description'
            )}
          </button>
        </div>
      )}

      {/* Success: JD summary */}
      {parseJD.isSuccess && parseJD.data && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">Job description parsed successfully</span>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-5">
            {/* Header */}
            <div>
              <p className="text-lg font-semibold text-gray-900">{title || 'Unknown title'}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-gray-500">
                {company    && <span>{company}</span>}
                {location   && <span>{location}</span>}
                {remoteType && <span className="capitalize">{remoteType.replace('_', ' ')}</span>}
              </div>
            </div>

            {/* Required skills */}
            {requiredSkills.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Required skills</p>
                <div className="flex flex-wrap gap-2">
                  {requiredSkills.map((s) => <Badge key={s} label={s} variant="red" />)}
                </div>
              </div>
            )}

            {/* Preferred skills */}
            {preferredSkills.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Preferred skills</p>
                <div className="flex flex-wrap gap-2">
                  {preferredSkills.map((s) => <Badge key={s} label={s} variant="blue" />)}
                </div>
              </div>
            )}

            {/* Keywords */}
            {keywords.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Keywords</p>
                <div className="flex flex-wrap gap-2">
                  {keywords.map((k) => <Badge key={k} label={k} variant="gray" />)}
                </div>
              </div>
            )}
          </div>

          {/* No resume warning */}
          {noResumeWarning && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                No resume found. Please{' '}
                <a href="/upload" className="font-medium underline">upload your resume</a>{' '}
                first before running a match.
              </span>
            </div>
          )}

          {/* Match error */}
          {match.isError && (
            <p className="flex items-center gap-1.5 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {match.error?.message ?? 'Match failed. Please try again.'}
            </p>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => parseJD.reset()}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Parse different JD
            </button>

            <button
              onClick={handleMatch}
              disabled={!currentResumeId || match.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {match.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running match…
                </>
              ) : (
                <>
                  Match with Resume
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
