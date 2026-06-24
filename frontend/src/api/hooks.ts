import { useMutation, useQuery } from '@tanstack/react-query'
import client from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ParsedResume {
  id: number
  parsedData: Record<string, unknown>
}

export interface ParsedJD {
  id: number
  parsedData: Record<string, unknown>
}

export interface MatchResult {
  id: number
  overallScore: number
  skillScore: number
  experienceScore: number
  keywordScore: number
  gapAnalysis: string
  ats_present: string[]
  ats_missing: string[]
  ats_coverage_percent: number
}

export interface RewriteResult {
  id: number
  rewriteData: string
  fidelityStatus: string
  fidelityScore: number | null
  rewriteAttempts: number
}

export interface InterviewSession {
  id: number
  sessionId: string
  status: string
  conversation: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/** POST /api/resumes/parse — multipart file upload */
export function useParseResume() {
  return useMutation<ParsedResume, Error, File>({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const { data } = await client.post<ParsedResume>('/resumes/parse', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return data
    },
  })
}

/** POST /api/jds/parse — raw text or URL */
export function useParseJD() {
  return useMutation<ParsedJD, Error, { text?: string; url?: string }>({
    mutationFn: async (payload) => {
      const { data } = await client.post<ParsedJD>('/jds/parse', payload)
      return data
    },
  })
}

/** POST /api/match */
export function useMatch() {
  return useMutation<MatchResult, Error, { resumeId: number; jdId: number }>({
    mutationFn: async (payload) => {
      const { data } = await client.post<MatchResult>('/match', payload)
      return data
    },
  })
}

/** POST /api/rewrite */
export function useRewrite() {
  return useMutation<
    RewriteResult,
    Error,
    { resumeId: number; jdId: number; matchResultId: number }
  >({
    mutationFn: async (payload) => {
      const { data } = await client.post<RewriteResult>('/rewrite', payload)
      return data
    },
  })
}

/** POST /api/interviews/start */
export function useStartInterview() {
  return useMutation<
    InterviewSession,
    Error,
    { resumeId: number; jdId: number }
  >({
    mutationFn: async (payload) => {
      const { data } = await client.post<InterviewSession>('/interviews/start', payload)
      return data
    },
  })
}

/** POST /api/interviews/{sessionId}/answer */
export function useAnswerInterview(sessionId: string) {
  return useMutation<InterviewSession, Error, { answer: string }>({
    mutationFn: async (payload) => {
      const { data } = await client.post<InterviewSession>(
        `/interviews/${sessionId}/answer`,
        payload
      )
      return data
    },
  })
}

/** POST /api/interviews/{sessionId}/end */
export function useEndInterview(sessionId: string) {
  return useMutation<InterviewSession, Error, void>({
    mutationFn: async () => {
      const { data } = await client.post<InterviewSession>(
        `/interviews/${sessionId}/end`
      )
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** GET /api/resumes/{id} */
export function useGetResume(id: number | null) {
  return useQuery<ParsedResume, Error>({
    queryKey: ['resume', id],
    queryFn: async () => {
      const { data } = await client.get<ParsedResume>(`/resumes/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

/** GET /api/jds/{id} */
export function useGetJD(id: number | null) {
  return useQuery<ParsedJD, Error>({
    queryKey: ['jd', id],
    queryFn: async () => {
      const { data } = await client.get<ParsedJD>(`/jds/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

/** GET /api/match/{id} */
export function useGetMatch(id: number | null) {
  return useQuery<MatchResult, Error>({
    queryKey: ['match', id],
    queryFn: async () => {
      const { data } = await client.get<MatchResult>(`/match/${id}`)
      return data
    },
    enabled: id !== null,
  })
}
