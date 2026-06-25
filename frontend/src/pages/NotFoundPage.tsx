import { useNavigate } from 'react-router-dom'
import { FileQuestion, Home } from 'lucide-react'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gray-50 p-6">
      {/* Illustration */}
      <div className="flex h-24 w-24 items-center justify-center rounded-3xl bg-indigo-50">
        <FileQuestion className="h-12 w-12 text-indigo-400" />
      </div>

      {/* Copy */}
      <div className="text-center space-y-2">
        <p className="text-6xl font-extrabold tabular-nums text-gray-200">404</p>
        <h1 className="text-xl font-bold text-gray-900">Page not found</h1>
        <p className="max-w-xs text-sm text-gray-500">
          The page you're looking for doesn't exist or has been moved.
        </p>
      </div>

      {/* Action */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors"
      >
        <Home className="h-4 w-4" />
        Back to Dashboard
      </button>
    </div>
  )
}
