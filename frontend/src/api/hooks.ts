import { useMutation, useQuery } from '@tanstack/react-query'
import client from './client'
import { parseParsedData } from './utils'

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
  /** Stored as a JSON string (full Python agent response) in the Spring Boot entity. */
  gapAnalysis?: string
  /** Present only in the POST /match response; absent from GET /match/{id}. */
  ats_present?: string[]
  ats_missing?: string[]
  ats_coverage_percent?: number
}

export interface RewriteResult {
  id: number
  rewriteData: string
  fidelityStatus: string
  fidelityScore: number | null
  rewriteAttempts: number
}

/**
 * Response from POST /api/interviews/start.
 * Keys are snake_case because the controller returns a plain Java Map.
 */
export interface StartInterviewResponse {
  db_id: number
  session_id: string
  question: string
  question_number: number
  total_questions: number
  type: string
  difficulty: string
}

/**
 * Response from GET /api/interviews/{sessionId}.
 * Keys are snake_case (plain Java Map). `agent_state` is the full Python
 * interview session state and contains conversation_history, questions,
 * answers, review, etc.
 */
export interface InterviewSession {
  db_id: number
  session_id: string
  status: string
  question_count: number
  started_at: string
  ended_at: string | null
  agent_state: Record<string, unknown>
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
      return parseParsedData(data)
    },
  })
}

/** POST /api/jds/parse — raw text or URL */
export function useParseJD() {
  return useMutation<ParsedJD, Error, { text?: string; url?: string }>({
    mutationFn: async (payload) => {
      const { data } = await client.post<ParsedJD>('/jds/parse', payload)
      return parseParsedData(data)
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
    StartInterviewResponse,
    Error,
    { resumeId: number; jdId: number; numQuestions?: number }
  >({
    mutationFn: async (payload) => {
      const { data } = await client.post<StartInterviewResponse>('/interviews/start', payload)
      return data
    },
  })
}

/**
 * POST /api/interviews/{sessionId}/answer
 * Returns the raw Python agent state (snake_case keys).
 */
export function useAnswerInterview(sessionId: string) {
  return useMutation<Record<string, unknown>, Error, { answer: string }>({
    mutationFn: async (payload) => {
      const { data } = await client.post<Record<string, unknown>>(
        `/interviews/${sessionId}/answer`,
        payload
      )
      return data
    },
  })
}

/**
 * POST /api/interviews/{sessionId}/end
 * Returns the raw Python agent state including the coach review.
 */
export function useEndInterview(sessionId: string) {
  return useMutation<Record<string, unknown>, Error, void>({
    mutationFn: async () => {
      const { data } = await client.post<Record<string, unknown>>(
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
      return parseParsedData(data)
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
      return parseParsedData(data)
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

/** GET /api/rewrite/{id} — Spring Boot entity; rewriteData is a JSON string */
export interface RewriteEntity {
  id: number
  rewriteData: string        // JSON-encoded RewriteResult from Python agent
  fidelityStatus: string
  fidelityScore: number | null
  rewriteAttempts: number
}

export function useGetRewrite(id: number | null) {
  return useQuery<RewriteEntity, Error>({
    queryKey: ['rewrite', id],
    queryFn: async () => {
      const { data } = await client.get<RewriteEntity>(`/rewrite/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

/** GET /api/interviews/{sessionId} — sessionId is the UUID string */
export function useGetInterview(id: string | null) {
  return useQuery<InterviewSession, Error>({
    queryKey: ['interview', id],
    queryFn: async () => {
      const { data } = await client.get<InterviewSession>(`/interviews/${id}`)
      return data
    },
    enabled: id !== null,
  })
}

// ---------------------------------------------------------------------------
// Recent-activity list hooks
// These endpoints may not be implemented yet; each falls back to [] on error.
// ---------------------------------------------------------------------------

export interface ResumeListItem {
  id: number
  createdAt?: string
  parsedData?: Record<string, unknown>
}

export interface MatchListItem {
  id: number
  overallScore: number
  skillScore?: number
  experienceScore?: number
  keywordScore?: number
  createdAt?: string
  resumeId?: number
  jdId?: number
}

export interface InterviewListItem {
  id: number
  sessionId: string
  status: string
  createdAt?: string
  questionCount?: number
}

export interface AgentRun {
  id: number
  agentType: string
  status: string
  createdAt?: string
  durationMs?: number
}

/** GET /api/resumes/recent — falls back to [] when endpoint is unavailable. */
export function useRecentResumes() {
  return useQuery<ResumeListItem[], Error>({
    queryKey: ['resumes', 'recent'],
    queryFn: async () => {
      try {
        const { data } = await client.get<ResumeListItem[]>('/resumes/recent')
        return data ?? []
      } catch {
        return []
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}

/** GET /api/match/recent — falls back to [] when endpoint is unavailable. */
export function useRecentMatches() {
  return useQuery<MatchListItem[], Error>({
    queryKey: ['matches', 'recent'],
    queryFn: async () => {
      try {
        const { data } = await client.get<MatchListItem[]>('/match/recent')
        return data ?? []
      } catch {
        return []
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}

/** GET /api/interviews/recent — falls back to [] when endpoint is unavailable. */
export function useRecentInterviews() {
  return useQuery<InterviewListItem[], Error>({
    queryKey: ['interviews', 'recent'],
    queryFn: async () => {
      try {
        const { data } = await client.get<InterviewListItem[]>('/interviews/recent')
        return data ?? []
      } catch {
        return []
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}

/** GET /api/agent-runs/recent?limit=10 — falls back to [] when endpoint is unavailable. */
export function useAgentRuns() {
  return useQuery<AgentRun[], Error>({
    queryKey: ['agent-runs', 'recent'],
    queryFn: async () => {
      try {
        const { data } = await client.get<AgentRun[]>('/agent-runs/recent?limit=10')
        return data ?? []
      } catch {
        return []
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}
