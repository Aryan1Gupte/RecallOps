export type MemoryType =
  | 'resolution'
  | 'failed_action'
  | 'procedure'
  | 'observation'

export type MemoryStatus = 'active' | 'superseded' | 'rejected'

export type MemoryFeedbackOutcome = 'success' | 'failure'

export interface Memory {
  id: string
  incident_id: string | null
  memory_type: MemoryType
  summary: string
  root_cause: string | null
  resolution: string | null
  embedding_text: string
  embedding_model_id: string
  embedding_dimension: number
  success_count: number
  failure_count: number
  reliability: number
  status: MemoryStatus
  superseded_by: string | null
  superseded_at: string | null
  supersession_reason: string | null
  created_at: string
  updated_at: string
  linked_incident_title: string | null
  linked_incident_service: string | null
  linked_incident_environment: string | null
  replacement_memory_summary: string | null
  replacement_memory_type: MemoryType | null
  replacement_memory_status: MemoryStatus | null
}

export interface MemoryCreateInput {
  incident_id?: string
  memory_type: MemoryType
  summary: string
  root_cause?: string
  resolution?: string
}

export interface MemoryListFilters {
  status?: MemoryStatus
  memory_type?: MemoryType
  incident_id?: string
}

export interface RecalledMemory {
  memory_id: string
  incident_id: string | null
  memory_type: MemoryType
  summary: string
  root_cause: string | null
  resolution: string | null
  status: MemoryStatus
  embedding_model_id: string
  embedding_dimension: number
  success_count: number
  failure_count: number
  superseded_by: string | null
  superseded_at: string | null
  supersession_reason: string | null
  replacement_memory_summary?: string | null
  replacement_memory_type?: MemoryType | null
  replacement_memory_status?: MemoryStatus | null
  cosine_distance: number
  similarity: number
  reliability: number
  same_service: boolean
  same_service_score: number
  final_score: number
  rank: number
  why_recalled: string
}

export interface MemoryRecallResponse {
  incident_id: string
  query_embedding_model_id: string
  query_embedding_dimension: number
  min_similarity: number
  top_k: number
  memories: RecalledMemory[]
  message: string
  ranking_formula: string
  candidate_count: number
  returned_count: number
}

export interface MemoryRecallOptions {
  top_k?: number
  min_similarity?: number
}

export interface MemoryFeedbackInput {
  outcome: MemoryFeedbackOutcome
}

export interface MemoryFeedbackResponse {
  memory_id: string
  outcome: MemoryFeedbackOutcome
  success_count: number
  failure_count: number
  reliability: number
  status: MemoryStatus
  updated_at: string
  message: string
}

export interface MemoryRejectInput {
  reason?: string
}

export interface MemoryRejectResponse {
  memory_id: string
  status: MemoryStatus
  supersession_reason: string | null
  updated_at: string
  message: string
}

export interface MemorySupersedeInput {
  superseded_by: string
  reason?: string
}

export interface MemorySupersedeResponse {
  memory_id: string
  status: MemoryStatus
  superseded_by: string | null
  superseded_at: string | null
  supersession_reason: string | null
  updated_at: string
  message: string
}

const API_BASE_PATH = '/api'

class MemoryApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MemoryApiError'
  }
}

function messageForStatus(status: number): string {
  if (status === 404) {
    return 'The requested memory or incident could not be found.'
  }
  if (status === 422) {
    return 'Please check the memory details and try again.'
  }
  if (status === 409) {
    return 'This memory action is only available for active memories.'
  }
  if (status === 502) {
    return 'The embedding service could not complete this memory request. Please try again.'
  }
  if (status === 503) {
    return 'RecallOps is temporarily unavailable. Please try again shortly.'
  }
  return 'RecallOps could not complete the memory request. Please try again.'
}

async function safeDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : null
  } catch {
    return null
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_PATH}${path}`, init)
  } catch {
    throw new MemoryApiError(
      'Unable to reach the RecallOps API. Confirm the backend is running and try again.',
    )
  }

  if (!response.ok) {
    throw new MemoryApiError(
      (await safeDetail(response)) ?? messageForStatus(response.status),
    )
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new MemoryApiError('RecallOps returned an unreadable response.')
  }
}

export function createMemory(input: MemoryCreateInput): Promise<Memory> {
  return request<Memory>('/memories', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })
}

export function listMemories(
  filters: MemoryListFilters = {},
): Promise<Memory[]> {
  const params = new URLSearchParams()
  if (filters.status) {
    params.set('status', filters.status)
  }
  if (filters.memory_type) {
    params.set('memory_type', filters.memory_type)
  }
  if (filters.incident_id) {
    params.set('incident_id', filters.incident_id)
  }
  const query = params.toString()
  return request<Memory[]>(`/memories${query ? `?${query}` : ''}`)
}

export function getMemory(id: string): Promise<Memory> {
  return request<Memory>(`/memories/${encodeURIComponent(id)}`)
}

export function recallIncidentMemories(
  incidentId: string,
  options: MemoryRecallOptions = {},
): Promise<MemoryRecallResponse> {
  const params = new URLSearchParams()
  if (options.top_k !== undefined) {
    params.set('top_k', String(options.top_k))
  }
  if (options.min_similarity !== undefined) {
    params.set('min_similarity', String(options.min_similarity))
  }
  const query = params.toString()
  return request<MemoryRecallResponse>(
    `/incidents/${encodeURIComponent(incidentId)}/memory-recall${
      query ? `?${query}` : ''
    }`,
    { method: 'POST' },
  )
}

export function submitMemoryFeedback(
  memoryId: string,
  input: MemoryFeedbackInput,
): Promise<MemoryFeedbackResponse> {
  return request<MemoryFeedbackResponse>(
    `/memories/${encodeURIComponent(memoryId)}/feedback`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
    },
  )
}

export function rejectMemory(
  memoryId: string,
  input: MemoryRejectInput = {},
): Promise<MemoryRejectResponse> {
  return request<MemoryRejectResponse>(
    `/memories/${encodeURIComponent(memoryId)}/reject`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
    },
  )
}

export function supersedeMemory(
  memoryId: string,
  input: MemorySupersedeInput,
): Promise<MemorySupersedeResponse> {
  return request<MemorySupersedeResponse>(
    `/memories/${encodeURIComponent(memoryId)}/supersede`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
    },
  )
}
