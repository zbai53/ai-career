import { X, AlertCircle, WifiOff, Info } from 'lucide-react'
import { useToastStore, type ToastType } from '../stores/toastStore'

function iconFor(type: ToastType) {
  if (type === 'warning') return WifiOff
  if (type === 'info')    return Info
  return AlertCircle
}

const STYLES: Record<ToastType, { wrapper: string; icon: string; text: string; btn: string }> = {
  error:   { wrapper: 'bg-red-50 border-red-200',    icon: 'text-red-500',    text: 'text-red-800',   btn: 'text-red-400 hover:text-red-600'   },
  warning: { wrapper: 'bg-amber-50 border-amber-200', icon: 'text-amber-500', text: 'text-amber-800', btn: 'text-amber-400 hover:text-amber-600' },
  info:    { wrapper: 'bg-blue-50 border-blue-200',   icon: 'text-blue-500',  text: 'text-blue-800',  btn: 'text-blue-400 hover:text-blue-600'   },
}

export default function ToastContainer() {
  const { toasts, dismiss } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-[min(22rem,calc(100vw-2rem))]">
      {toasts.map((toast) => {
        const s = STYLES[toast.type]
        const Icon = iconFor(toast.type)
        return (
          <div
            key={toast.id}
            className={`flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg animate-[page-fade-in_0.18s_ease-out_both] ${s.wrapper}`}
          >
            <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${s.icon}`} />
            <p className={`flex-1 text-sm leading-snug ${s.text}`}>{toast.message}</p>
            <button
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss"
              className={`shrink-0 rounded p-0.5 transition-colors ${s.btn}`}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
