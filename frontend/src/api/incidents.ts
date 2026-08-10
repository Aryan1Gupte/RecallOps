import type { MemoryStatus, MemoryType } from './memories'

export type IncidentStatus = 'open' | 'investigating' | 'resolved'

export type IncidentEnvironment =
  | 'development'
  | 'test'
  | 'uat'
  | 'production'

export interface Incident {
  id: string
  title: string
  description: string
  service: string
  environment: IncidentEnvironment
  status: IncidentStatus
  created_at: string
  updated_at: string
}

export interface IncidentCreateInput {
  title: string
  description: string
  service: string
  environment: IncidentEnvironment
}

export interface IncidentAnalysis {
  incident_id: string
  summary: string
  likely_category: string
  hypotheses: string[]
  recommended_next_steps: string[]
  cautions: string[]
  model_id: string
}

export interface IncidentEmbeddingPreview {
  incident_id: string
  model_id: string
  dimension: number
  input_text_token_count: number
  text_preview: string
}

export interface AgentRecalledMemory {
  rank: number
  memory_type: MemoryType
  status: MemoryStatus
  summary: string
  root_cause: string | null
  resolution: string | null
  success_count: number
  failure_count: number
  similarity: number
  reliability: number
  final_score: number
  why_recalled: string
}

export interface MemoryAssistedRecommendation {
  incident_id: string
  summary: string
  memory_used: boolean
  recalled_memory_count: number
  memory_grounded_findings: string[]
  likely_root_cause: string
  recommended_next_steps: string[]
  cautions: string[]
  memory_influence_notes: string[]
  recalled_memories: AgentRecalledMemory[]
  model_id: string
}

const API_BASE_PATH = '/api'

class IncidentApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'IncidentApiError'
  }
}

function messageForStatus(status: number): string {
  if (status === 404) {
    return 'The requested incident could not be found.'
  }
  if (status === 422) {
    return 'Please check the incident details and try again.'
  }
  if (status === 502) {
    return 'The AI service could not produce a valid result. Please try again.'
  }
  if (status === 503) {
    return 'RecallOps is temporarily unavailable. Please try again shortly.'
  }
  if (status === 429) {
    return 'RecallOps is limiting paid AI requests for demo safety. Please try again shortly.'
  }
  return 'RecallOps could not complete the request. Please try again.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_PATH}${path}`, init)
  } catch {
    throw new IncidentApiError(
      'Unable to reach the RecallOps API. Confirm the backend is running and try again.',
    )
  }

  if (!response.ok) {
    throw new IncidentApiError(messageForStatus(response.status))
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new IncidentApiError('RecallOps returned an unreadable response.')
  }
}

export function listIncidents(): Promise<Incident[]> {
  return request<Incident[]>('/incidents')
}

export function createIncident(input: IncidentCreateInput): Promise<Incident> {
  return request<Incident>('/incidents', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })
}

export function getIncident(id: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}`)
}

export function analyzeIncident(id: string): Promise<IncidentAnalysis> {
  return request<IncidentAnalysis>(
    `/incidents/${encodeURIComponent(id)}/analysis`,
    { method: 'POST' },
  )
}

export function generateEmbeddingPreview(
  id: string,
): Promise<IncidentEmbeddingPreview> {
  return request<IncidentEmbeddingPreview>(
    `/incidents/${encodeURIComponent(id)}/embedding-preview`,
    { method: 'POST' },
  )
}

export function runMemoryAssistedRecommendation(
  id: string,
): Promise<MemoryAssistedRecommendation> {
  return request<MemoryAssistedRecommendation>(
    `/incidents/${encodeURIComponent(id)}/agent-recommendation`,
    { method: 'POST' },
  )
}
