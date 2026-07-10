export type MemoryType =
  | 'resolution'
  | 'failed_action'
  | 'procedure'
  | 'observation'

export type MemoryStatus = 'active' | 'superseded' | 'rejected'

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
  status: MemoryStatus
  superseded_by: string | null
  superseded_at: string | null
  supersession_reason: string | null
  created_at: string
  updated_at: string
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
  if (status === 502) {
    return 'The embedding service could not save this memory. Please try again.'
  }
  if (status === 503) {
    return 'RecallOps is temporarily unavailable. Please try again shortly.'
  }
  return 'RecallOps could not complete the memory request. Please try again.'
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
    throw new MemoryApiError(messageForStatus(response.status))
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
