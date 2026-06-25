import { create } from 'zustand'

export type ToastType = 'error' | 'warning' | 'info'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

interface ToastStore {
  toasts: Toast[]
  show: (message: string, type?: ToastType) => void
  dismiss: (id: number) => void
}

let nextId = 0

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  show: (message, type = 'error') => {
    const id = ++nextId
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }))
    // Auto-dismiss after 5 s
    setTimeout(
      () => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
      5000
    )
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Call this outside React (e.g. in axios interceptors). */
export function showToast(message: string, type: ToastType = 'error') {
  useToastStore.getState().show(message, type)
}
