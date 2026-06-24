import { useRef, useState, DragEvent, ChangeEvent } from 'react'
import { UploadCloud, FileText, X, Loader2 } from 'lucide-react'

interface FileUploadProps {
  onUpload: (file: File) => void
  isLoading: boolean
  error: string | null
  accept?: string
}

const ACCEPTED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
const ACCEPTED_LABEL = '.pdf, .docx'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUpload({ onUpload, isLoading, error }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [typeError, setTypeError] = useState<string | null>(null)

  function validate(file: File): boolean {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setTypeError(`Unsupported file type. Please upload a ${ACCEPTED_LABEL} file.`)
      return false
    }
    setTypeError(null)
    return true
  }

  function handleFile(file: File) {
    if (validate(file)) setSelectedFile(file)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function handleRemove() {
    setSelectedFile(null)
    setTypeError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const displayError = typeError ?? error

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onClick={() => !selectedFile && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors
          ${selectedFile
            ? 'cursor-default border-indigo-300 bg-indigo-50'
            : isDragging
              ? 'cursor-copy border-indigo-500 bg-indigo-50'
              : 'cursor-pointer border-gray-300 bg-white hover:border-indigo-400 hover:bg-gray-50'
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="sr-only"
          onChange={handleChange}
        />

        {selectedFile ? (
          <>
            <FileText className="h-10 w-10 text-indigo-500" />
            <div>
              <p className="font-medium text-gray-900">{selectedFile.name}</p>
              <p className="text-sm text-gray-500">{formatBytes(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); handleRemove() }}
              className="absolute right-3 top-3 rounded-full p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          </>
        ) : (
          <>
            <UploadCloud className={`h-10 w-10 ${isDragging ? 'text-indigo-500' : 'text-gray-400'}`} />
            <div>
              <p className="font-medium text-gray-700">
                Drop your resume here, or{' '}
                <span className="text-indigo-600 underline underline-offset-2">browse</span>
              </p>
              <p className="mt-1 text-sm text-gray-500">Supports {ACCEPTED_LABEL}</p>
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {displayError && (
        <p className="text-sm text-red-600">{displayError}</p>
      )}

      {/* Upload button */}
      <button
        type="button"
        disabled={!selectedFile || isLoading}
        onClick={() => selectedFile && onUpload(selectedFile)}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Parsing resume…
          </>
        ) : (
          <>
            <UploadCloud className="h-4 w-4" />
            Upload &amp; Parse
          </>
        )}
      </button>
    </div>
  )
}
