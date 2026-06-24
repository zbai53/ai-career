import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface WorkflowState {
  currentResumeId: number | null
  currentJDId: number | null
  currentMatchId: number | null
  currentInterviewId: string | null
  setResumeId: (id: number) => void
  setJDId: (id: number) => void
  setMatchId: (id: number) => void
  setInterviewId: (id: string) => void
  reset: () => void
}

const initialState = {
  currentResumeId: null,
  currentJDId: null,
  currentMatchId: null,
  currentInterviewId: null,
}

export const useWorkflowStore = create<WorkflowState>()(
  persist(
    (set) => ({
      ...initialState,
      setResumeId: (id) => set({ currentResumeId: id }),
      setJDId: (id) => set({ currentJDId: id }),
      setMatchId: (id) => set({ currentMatchId: id }),
      setInterviewId: (id) => set({ currentInterviewId: id }),
      reset: () => set(initialState),
    }),
    {
      name: 'workflow-storage',
      partialize: (state) => ({
        currentResumeId: state.currentResumeId,
        currentJDId: state.currentJDId,
        currentMatchId: state.currentMatchId,
        currentInterviewId: state.currentInterviewId,
      }),
    }
  )
)
