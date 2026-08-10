import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

import {
  analyzeIncident,
  createIncident,
  generateEmbeddingPreview,
  getIncident,
  listIncidents,
  runMemoryAssistedRecommendation,
  type AgentRecalledMemory,
  type Incident,
  type IncidentAnalysis,
  type IncidentCreateInput,
  type IncidentEmbeddingPreview,
  type IncidentEnvironment,
  type MemoryAssistedRecommendation,
} from './api/incidents'
import {
  createMemory,
  listMemories,
  recallIncidentMemories,
  rejectMemory,
  submitMemoryFeedback,
  supersedeMemory,
  type Memory,
  type MemoryCreateInput,
  type MemoryFeedbackOutcome,
  type MemoryFeedbackResponse,
  type MemoryRejectResponse,
  type MemoryRecallResponse,
  type MemoryStatus,
  type MemorySupersedeResponse,
  type MemoryType,
} from './api/memories'

const emptyForm: IncidentCreateInput = {
  title: '',
  description: '',
  service: '',
  environment: 'development',
}

const environments: IncidentEnvironment[] = [
  'development',
  'test',
  'uat',
  'production',
]

const memoryTypes: MemoryType[] = [
  'resolution',
  'failed_action',
  'procedure',
  'observation',
]

interface MemoryFormState {
  memory_type: MemoryType
  summary: string
  root_cause: string
  resolution: string
}

interface SupersedeFormState {
  superseded_by: string
  reason: string
}

type MemoryLifecycleAction = 'reject' | 'supersede'
type InspectorStatusFilter = 'all' | MemoryStatus
type InspectorMemoryTypeFilter = 'all' | MemoryType
type DetailTab = 'recommendation' | 'recall' | 'memory' | 'advanced'

// Matches the seeded demo prefix, including the legacy form without a
// trailing space. Used for display and filtering only; no data is mutated.
const DEMO_INCIDENT_PREFIX = 'Demo —'

function isDemoIncident(incident: Incident): boolean {
  return incident.title.startsWith(DEMO_INCIDENT_PREFIX)
}

const emptyMemoryForm: MemoryFormState = {
  memory_type: 'resolution',
  summary: '',
  root_cause: '',
  resolution: '',
}

function newMemoryForm(): MemoryFormState {
  return { ...emptyMemoryForm }
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'Unknown time'
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function readableError(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Something unexpected happened. Please try again.'
}

function formatMemoryType(value: MemoryType): string {
  return value.replace(/_/g, ' ')
}

function formatSimilarity(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatDistance(value: number): string {
  return value.toFixed(4)
}

function shortId(value: string): string {
  return value.slice(0, 8)
}

function truncateText(value: string, maxLength = 64): string {
  if (value.length <= maxLength) {
    return value
  }
  return `${value.slice(0, maxLength - 1)}…`
}

function formatReplacementOption(memory: Memory): string {
  return `${formatMemoryType(memory.memory_type)} · ${truncateText(
    memory.summary,
  )} · ${memory.status} · ${shortId(memory.id)}`
}

function renderAdvancedDetails(children: ReactNode) {
  return (
    <details className="advanced-details">
      <summary>Advanced details</summary>
      <div className="advanced-details-content">{children}</div>
    </details>
  )
}

export default function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [form, setForm] = useState<IncidentCreateInput>(emptyForm)
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [agentRecommendation, setAgentRecommendation] =
    useState<MemoryAssistedRecommendation | null>(null)
  const [agentRecommendationError, setAgentRecommendationError] = useState<
    string | null
  >(null)
  const [isRunningAgentRecommendation, setIsRunningAgentRecommendation] =
    useState(false)
  const [embeddingPreview, setEmbeddingPreview] =
    useState<IncidentEmbeddingPreview | null>(null)
  const [embeddingError, setEmbeddingError] = useState<string | null>(null)
  const [isEmbedding, setIsEmbedding] = useState(false)
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoryForm, setMemoryForm] =
    useState<MemoryFormState>(emptyMemoryForm)
  const [memoryListError, setMemoryListError] = useState<string | null>(null)
  const [memoryFormError, setMemoryFormError] = useState<string | null>(null)
  const [isMemoryListLoading, setIsMemoryListLoading] = useState(false)
  const [isSavingMemory, setIsSavingMemory] = useState(false)
  const [memoryRecall, setMemoryRecall] = useState<MemoryRecallResponse | null>(
    null,
  )
  const [memoryRecallError, setMemoryRecallError] = useState<string | null>(null)
  const [isRecallingMemories, setIsRecallingMemories] = useState(false)
  const [feedbackPendingMemoryIds, setFeedbackPendingMemoryIds] = useState<
    Record<string, boolean>
  >({})
  const [feedbackMessages, setFeedbackMessages] = useState<
    Record<string, string>
  >({})
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string>>(
    {},
  )
  const [lifecyclePendingByMemory, setLifecyclePendingByMemory] = useState<
    Record<string, MemoryLifecycleAction>
  >({})
  const [lifecycleMessages, setLifecycleMessages] = useState<
    Record<string, string>
  >({})
  const [lifecycleErrors, setLifecycleErrors] = useState<Record<string, string>>(
    {},
  )
  const [rejectReasons, setRejectReasons] = useState<Record<string, string>>({})
  const [supersedeForms, setSupersedeForms] = useState<
    Record<string, SupersedeFormState>
  >({})
  const [inspectorMemories, setInspectorMemories] = useState<Memory[]>([])
  const [isInspectorLoading, setIsInspectorLoading] = useState(false)
  const [inspectorError, setInspectorError] = useState<string | null>(null)
  const [activeDetailTab, setActiveDetailTab] =
    useState<DetailTab>('recommendation')
  const [showDemoIncidentsOnly, setShowDemoIncidentsOnly] = useState(false)
  const [inspectorStatusFilter, setInspectorStatusFilter] =
    useState<InspectorStatusFilter>('all')
  const [inspectorTypeFilter, setInspectorTypeFilter] =
    useState<InspectorMemoryTypeFilter>('all')
  const detailRequestId = useRef(0)
  const analysisRequestId = useRef(0)
  const agentRecommendationRequestId = useRef(0)
  const embeddingRequestId = useRef(0)
  const memoryRequestId = useRef(0)
  const saveMemoryRequestId = useRef(0)
  const recallRequestId = useRef(0)
  const inspectorRequestId = useRef(0)
  const selectedIncidentIdRef = useRef<string | null>(null)
  const feedbackPendingMemoryIdsRef = useRef<Record<string, boolean>>({})
  const lifecyclePendingByMemoryRef = useRef<
    Record<string, MemoryLifecycleAction>
  >({})

  useEffect(() => {
    let isActive = true

    async function loadIncidents() {
      try {
        const loadedIncidents = await listIncidents()
        if (isActive) {
          setIncidents(loadedIncidents)
          setListError(null)
        }
      } catch (error) {
        if (isActive) {
          setListError(readableError(error))
        }
      } finally {
        if (isActive) {
          setIsLoading(false)
        }
      }
    }

    void loadIncidents()
    return () => {
      isActive = false
    }
  }, [])

  useEffect(() => {
    const requestId = inspectorRequestId.current + 1
    inspectorRequestId.current = requestId
    setIsInspectorLoading(true)
    void refreshMemoryInspector(requestId)
  }, [])

  function updateForm<K extends keyof IncidentCreateInput>(
    field: K,
    value: IncidentCreateInput[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function updateMemoryForm<K extends keyof MemoryFormState>(
    field: K,
    value: MemoryFormState[K],
  ) {
    setMemoryForm((current) => ({ ...current, [field]: value }))
  }

  function setCurrentIncident(incident: Incident | null) {
    selectedIncidentIdRef.current = incident?.id ?? null
    setSelectedIncident(incident)
  }

  function isIncidentStillSelected(incidentId: string | null) {
    return incidentId !== null && selectedIncidentIdRef.current === incidentId
  }

  function startFeedbackPending(memoryId: string): boolean {
    if (feedbackPendingMemoryIdsRef.current[memoryId]) {
      return false
    }
    const next = {
      ...feedbackPendingMemoryIdsRef.current,
      [memoryId]: true,
    }
    feedbackPendingMemoryIdsRef.current = next
    setFeedbackPendingMemoryIds(next)
    return true
  }

  function finishFeedbackPending(memoryId: string) {
    if (!feedbackPendingMemoryIdsRef.current[memoryId]) {
      return
    }
    const next = { ...feedbackPendingMemoryIdsRef.current }
    delete next[memoryId]
    feedbackPendingMemoryIdsRef.current = next
    setFeedbackPendingMemoryIds(next)
  }

  function startLifecyclePending(
    memoryId: string,
    action: MemoryLifecycleAction,
  ): boolean {
    if (lifecyclePendingByMemoryRef.current[memoryId]) {
      return false
    }
    const next = {
      ...lifecyclePendingByMemoryRef.current,
      [memoryId]: action,
    }
    lifecyclePendingByMemoryRef.current = next
    setLifecyclePendingByMemory(next)
    return true
  }

  function finishLifecyclePending(
    memoryId: string,
    action: MemoryLifecycleAction,
  ) {
    if (lifecyclePendingByMemoryRef.current[memoryId] !== action) {
      return
    }
    const next = { ...lifecyclePendingByMemoryRef.current }
    delete next[memoryId]
    lifecyclePendingByMemoryRef.current = next
    setLifecyclePendingByMemory(next)
  }

  async function refreshMemoriesForIncident(
    incidentId: string,
    requestId: number,
  ) {
    try {
      const loadedMemories = await listMemories({ incident_id: incidentId })
      if (memoryRequestId.current === requestId) {
        setMemories(loadedMemories)
        setMemoryListError(null)
      }
    } catch (error) {
      if (memoryRequestId.current === requestId) {
        setMemoryListError(readableError(error))
      }
    } finally {
      if (memoryRequestId.current === requestId) {
        setIsMemoryListLoading(false)
      }
    }
  }

  async function refreshMemoryInspector(requestId: number) {
    try {
      const loadedMemories = await listMemories()
      if (inspectorRequestId.current === requestId) {
        setInspectorMemories(loadedMemories)
        setInspectorError(null)
      }
    } catch (error) {
      if (inspectorRequestId.current === requestId) {
        setInspectorError(readableError(error))
      }
    } finally {
      if (inspectorRequestId.current === requestId) {
        setIsInspectorLoading(false)
      }
    }
  }

  function startMemoryInspectorRefresh() {
    const requestId = inspectorRequestId.current + 1
    inspectorRequestId.current = requestId
    setIsInspectorLoading(true)
    void refreshMemoryInspector(requestId)
  }

  function applyFeedbackResult(
    memoryId: string,
    result: MemoryFeedbackResponse,
    incidentIdAtRequest: string | null,
  ) {
    if (isIncidentStillSelected(incidentIdAtRequest)) {
      setMemoryRecall((current) => {
        if (!current) {
          return current
        }
        return {
          ...current,
          memories: current.memories.map((memory) =>
            memory.memory_id === memoryId
              ? {
                  ...memory,
                  success_count: result.success_count,
                  failure_count: result.failure_count,
                  reliability: result.reliability,
                  status: result.status,
                }
              : memory,
          ),
        }
      })
      setMemories((current) =>
        current.map((memory) =>
          memory.id === memoryId
            ? {
                ...memory,
                success_count: result.success_count,
                failure_count: result.failure_count,
                reliability: result.reliability,
                status: result.status,
                updated_at: result.updated_at,
              }
            : memory,
        ),
      )
    }
    setInspectorMemories((current) =>
      current.map((memory) =>
        memory.id === memoryId
          ? {
              ...memory,
              success_count: result.success_count,
              failure_count: result.failure_count,
              reliability: result.reliability,
              status: result.status,
              updated_at: result.updated_at,
            }
          : memory,
      ),
    )
  }

  function applyLifecycleResult(
    memoryId: string,
    result: MemoryRejectResponse | MemorySupersedeResponse,
    incidentIdAtRequest: string | null,
  ) {
    const supersededBy =
      'superseded_by' in result ? result.superseded_by : null
    const supersededAt =
      'superseded_at' in result ? result.superseded_at : null
    const replacementSummary =
      'replacement_memory_summary' in result
        ? result.replacement_memory_summary
        : null
    const replacementType =
      'replacement_memory_type' in result ? result.replacement_memory_type : null
    const replacementStatus =
      'replacement_memory_status' in result
        ? result.replacement_memory_status
        : null

    if (isIncidentStillSelected(incidentIdAtRequest)) {
      setMemoryRecall((current) => {
        if (!current) {
          return current
        }
        return {
          ...current,
          memories: current.memories.map((memory) =>
            memory.memory_id === memoryId
              ? {
                  ...memory,
                  status: result.status,
                  superseded_by: supersededBy,
                  superseded_at: supersededAt,
                  supersession_reason: result.supersession_reason,
                  replacement_memory_summary: replacementSummary,
                  replacement_memory_type: replacementType,
                  replacement_memory_status: replacementStatus,
                }
              : memory,
          ),
        }
      })
      setMemories((current) =>
        current.map((memory) =>
          memory.id === memoryId
            ? {
                ...memory,
                status: result.status,
                superseded_by: supersededBy,
                superseded_at: supersededAt,
                supersession_reason: result.supersession_reason,
                replacement_memory_summary: replacementSummary,
                replacement_memory_type: replacementType,
                replacement_memory_status: replacementStatus,
                updated_at: result.updated_at,
              }
            : memory,
        ),
      )
    }
    setInspectorMemories((current) =>
      current.map((memory) =>
        memory.id === memoryId
          ? {
              ...memory,
              status: result.status,
              superseded_by: supersededBy,
              superseded_at: supersededAt,
              supersession_reason: result.supersession_reason,
              replacement_memory_summary: replacementSummary,
              replacement_memory_type: replacementType,
              replacement_memory_status: replacementStatus,
              updated_at: result.updated_at,
            }
          : memory,
      ),
    )
  }

  function clearLifecycleMessages(memoryId: string) {
    setLifecycleErrors((current) => {
      const next = { ...current }
      delete next[memoryId]
      return next
    })
    setLifecycleMessages((current) => {
      const next = { ...current }
      delete next[memoryId]
      return next
    })
  }

  function setRejectReason(memoryId: string, reason: string) {
    setRejectReasons((current) => ({ ...current, [memoryId]: reason }))
  }

  function updateSupersedeForm(
    memoryId: string,
    field: keyof SupersedeFormState,
    value: string,
  ) {
    setSupersedeForms((current) => ({
      ...current,
      [memoryId]: {
        superseded_by: current[memoryId]?.superseded_by ?? '',
        reason: current[memoryId]?.reason ?? '',
        [field]: value,
      },
    }))
  }

  function refreshSelectedIncidentMemories(expectedIncidentId: string | null) {
    const currentIncidentId = selectedIncidentIdRef.current
    if (
      currentIncidentId === null ||
      expectedIncidentId === null ||
      currentIncidentId !== expectedIncidentId
    ) {
      return
    }
    const requestId = memoryRequestId.current + 1
    memoryRequestId.current = requestId
    setIsMemoryListLoading(true)
    void refreshMemoriesForIncident(currentIncidentId, requestId)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const input: IncidentCreateInput = {
      title: form.title.trim(),
      description: form.description.trim(),
      service: form.service.trim(),
      environment: form.environment,
    }

    if (!input.title || !input.description || !input.service) {
      setFormError('Title, description, and service are required.')
      return
    }

    setIsCreating(true)
    setFormError(null)

    try {
      const created = await createIncident(input)
      setIncidents((current) => [
        created,
        ...current.filter((incident) => incident.id !== created.id),
      ])
      detailRequestId.current += 1
      analysisRequestId.current += 1
      agentRecommendationRequestId.current += 1
      embeddingRequestId.current += 1
      memoryRequestId.current += 1
      saveMemoryRequestId.current += 1
      recallRequestId.current += 1
      setCurrentIncident(created)
      setListError(null)
      setDetailError(null)
      setAnalysis(null)
      setAnalysisError(null)
      setIsAnalyzing(false)
      setAgentRecommendation(null)
      setAgentRecommendationError(null)
      setIsRunningAgentRecommendation(false)
      setEmbeddingPreview(null)
      setEmbeddingError(null)
      setIsEmbedding(false)
      setMemories([])
      setMemoryForm(newMemoryForm())
      setMemoryListError(null)
      setMemoryFormError(null)
      setIsMemoryListLoading(false)
      setIsSavingMemory(false)
      setActiveDetailTab('recommendation')
      setMemoryRecall(null)
      setMemoryRecallError(null)
      setIsRecallingMemories(false)
      setFeedbackMessages({})
      setFeedbackErrors({})
      setLifecycleMessages({})
      setLifecycleErrors({})
      setRejectReasons({})
      setSupersedeForms({})
      setForm(emptyForm)
    } catch (error) {
      setFormError(readableError(error))
    } finally {
      setIsCreating(false)
    }
  }

  async function handleSelect(incident: Incident) {
    const requestId = detailRequestId.current + 1
    detailRequestId.current = requestId
    analysisRequestId.current += 1
    agentRecommendationRequestId.current += 1
    embeddingRequestId.current += 1
    saveMemoryRequestId.current += 1
    recallRequestId.current += 1
    const selectedMemoryRequestId = memoryRequestId.current + 1
    memoryRequestId.current = selectedMemoryRequestId
    setCurrentIncident(incident)
    setIsDetailLoading(true)
    setDetailError(null)
    setAnalysis(null)
    setAnalysisError(null)
    setIsAnalyzing(false)
    setAgentRecommendation(null)
    setAgentRecommendationError(null)
    setIsRunningAgentRecommendation(false)
    setEmbeddingPreview(null)
    setEmbeddingError(null)
    setIsEmbedding(false)
    setMemories([])
    setMemoryForm(newMemoryForm())
    setMemoryListError(null)
    setMemoryFormError(null)
    setIsMemoryListLoading(true)
    setIsSavingMemory(false)
    setActiveDetailTab('recommendation')
    setMemoryRecall(null)
    setMemoryRecallError(null)
    setIsRecallingMemories(false)
    setFeedbackMessages({})
    setFeedbackErrors({})
    setLifecycleMessages({})
    setLifecycleErrors({})
    setRejectReasons({})
    setSupersedeForms({})

    void refreshMemoriesForIncident(incident.id, selectedMemoryRequestId)

    try {
      const detail = await getIncident(incident.id)
      if (detailRequestId.current === requestId) {
        setCurrentIncident(detail)
      }
    } catch (error) {
      if (detailRequestId.current === requestId) {
        setDetailError(readableError(error))
      }
    } finally {
      if (detailRequestId.current === requestId) {
        setIsDetailLoading(false)
      }
    }
  }

  async function handleAnalyze() {
    if (!selectedIncident) {
      return
    }

    const requestId = analysisRequestId.current + 1
    analysisRequestId.current = requestId
    const incidentId = selectedIncident.id
    setIsAnalyzing(true)
    setAnalysisError(null)

    try {
      const result = await analyzeIncident(incidentId)
      if (analysisRequestId.current === requestId) {
        setAnalysis(result)
      }
    } catch (error) {
      if (analysisRequestId.current === requestId) {
        setAnalysisError(readableError(error))
      }
    } finally {
      if (analysisRequestId.current === requestId) {
        setIsAnalyzing(false)
      }
    }
  }

  async function handleMemoryAssistedRecommendation() {
    if (!selectedIncident) {
      return
    }

    const requestId = agentRecommendationRequestId.current + 1
    agentRecommendationRequestId.current = requestId
    const incidentId = selectedIncident.id
    setIsRunningAgentRecommendation(true)
    setAgentRecommendationError(null)

    try {
      const result = await runMemoryAssistedRecommendation(incidentId)
      if (
        agentRecommendationRequestId.current === requestId &&
        isIncidentStillSelected(incidentId)
      ) {
        setAgentRecommendation(result)
      }
    } catch (error) {
      if (
        agentRecommendationRequestId.current === requestId &&
        isIncidentStillSelected(incidentId)
      ) {
        setAgentRecommendationError(readableError(error))
      }
    } finally {
      if (agentRecommendationRequestId.current === requestId) {
        setIsRunningAgentRecommendation(false)
      }
    }
  }

  async function handleEmbeddingPreview() {
    if (!selectedIncident) {
      return
    }

    const requestId = embeddingRequestId.current + 1
    embeddingRequestId.current = requestId
    const incidentId = selectedIncident.id
    setIsEmbedding(true)
    setEmbeddingError(null)

    try {
      const result = await generateEmbeddingPreview(incidentId)
      if (embeddingRequestId.current === requestId) {
        setEmbeddingPreview(result)
      }
    } catch (error) {
      if (embeddingRequestId.current === requestId) {
        setEmbeddingError(readableError(error))
      }
    } finally {
      if (embeddingRequestId.current === requestId) {
        setIsEmbedding(false)
      }
    }
  }

  async function handleCreateMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedIncident) {
      return
    }
    const incidentId = selectedIncident.id

    const input: MemoryCreateInput = {
      incident_id: incidentId,
      memory_type: memoryForm.memory_type,
      summary: memoryForm.summary.trim(),
    }
    const rootCause = memoryForm.root_cause.trim()
    const resolution = memoryForm.resolution.trim()
    if (rootCause) {
      input.root_cause = rootCause
    }
    if (resolution) {
      input.resolution = resolution
    }

    if (!input.summary) {
      setMemoryFormError('Summary is required.')
      return
    }

    const saveRequestId = saveMemoryRequestId.current + 1
    saveMemoryRequestId.current = saveRequestId
    setIsSavingMemory(true)
    setMemoryFormError(null)
    setMemoryListError(null)

    try {
      await createMemory(input)
      if (
        saveMemoryRequestId.current === saveRequestId &&
        isIncidentStillSelected(incidentId)
      ) {
        const listRequestId = memoryRequestId.current + 1
        memoryRequestId.current = listRequestId
        setMemoryForm(emptyMemoryForm)
        setIsMemoryListLoading(true)
        setMemoryRecall(null)
        setMemoryRecallError(null)
        setFeedbackMessages({})
        setFeedbackErrors({})
        setLifecycleMessages({})
        setLifecycleErrors({})
        setRejectReasons({})
        setSupersedeForms({})
        await refreshMemoriesForIncident(incidentId, listRequestId)
      }
      startMemoryInspectorRefresh()
    } catch (error) {
      if (
        saveMemoryRequestId.current === saveRequestId &&
        isIncidentStillSelected(incidentId)
      ) {
        setMemoryFormError(readableError(error))
      }
    } finally {
      if (saveMemoryRequestId.current === saveRequestId) {
        setIsSavingMemory(false)
      }
    }
  }

  async function handleRecallMemories() {
    if (!selectedIncident) {
      return
    }

    const requestId = recallRequestId.current + 1
    recallRequestId.current = requestId
    const incidentId = selectedIncident.id
    setIsRecallingMemories(true)
    setMemoryRecallError(null)
    setFeedbackMessages({})
    setFeedbackErrors({})
    setLifecycleMessages({})
    setLifecycleErrors({})

    try {
      const result = await recallIncidentMemories(incidentId)
      if (
        recallRequestId.current === requestId &&
        isIncidentStillSelected(incidentId)
      ) {
        setMemoryRecall(result)
      }
    } catch (error) {
      if (recallRequestId.current === requestId) {
        setMemoryRecallError(readableError(error))
      }
    } finally {
      if (recallRequestId.current === requestId) {
        setIsRecallingMemories(false)
      }
    }
  }

  async function handleMemoryFeedback(
    memoryId: string,
    outcome: MemoryFeedbackOutcome,
  ) {
    if (!startFeedbackPending(memoryId)) {
      return
    }
    const incidentIdAtRequest = selectedIncidentIdRef.current
    setFeedbackErrors((current) => {
      const next = { ...current }
      delete next[memoryId]
      return next
    })
    setFeedbackMessages((current) => {
      const next = { ...current }
      delete next[memoryId]
      return next
    })

    try {
      const result = await submitMemoryFeedback(memoryId, { outcome })
      applyFeedbackResult(memoryId, result, incidentIdAtRequest)
      setFeedbackMessages((current) => ({
        ...current,
        [memoryId]: `${result.message} Reliability updated. Recall again to refresh final ranking.`,
      }))
    } catch (error) {
      setFeedbackErrors((current) => ({
        ...current,
        [memoryId]: readableError(error),
      }))
    } finally {
      finishFeedbackPending(memoryId)
    }
  }

  async function handleRejectMemory(memoryId: string) {
    if (!startLifecyclePending(memoryId, 'reject')) {
      return
    }
    const incidentIdAtRequest = selectedIncidentIdRef.current
    clearLifecycleMessages(memoryId)

    const reason = rejectReasons[memoryId]?.trim()

    try {
      const result = await rejectMemory(memoryId, reason ? { reason } : {})
      applyLifecycleResult(memoryId, result, incidentIdAtRequest)
      setLifecycleMessages((current) => ({
        ...current,
        [memoryId]: `${result.message} It will be preserved but excluded from future recall.`,
      }))
      setRejectReasons((current) => {
        const next = { ...current }
        delete next[memoryId]
        return next
      })
      refreshSelectedIncidentMemories(incidentIdAtRequest)
      startMemoryInspectorRefresh()
    } catch (error) {
      setLifecycleErrors((current) => ({
        ...current,
        [memoryId]: readableError(error),
      }))
    } finally {
      finishLifecyclePending(memoryId, 'reject')
    }
  }

  async function handleSupersedeMemory(memoryId: string) {
    const formState = supersedeForms[memoryId] ?? {
      superseded_by: '',
      reason: '',
    }
    const supersededBy = formState.superseded_by.trim()
    const reason = formState.reason.trim()

    clearLifecycleMessages(memoryId)
    if (!supersededBy) {
      setLifecycleErrors((current) => ({
        ...current,
        [memoryId]: 'Choose an active replacement memory.',
      }))
      return
    }

    if (!startLifecyclePending(memoryId, 'supersede')) {
      return
    }
    const incidentIdAtRequest = selectedIncidentIdRef.current

    try {
      const result = await supersedeMemory(memoryId, {
        superseded_by: supersededBy,
        ...(reason ? { reason } : {}),
      })
      applyLifecycleResult(memoryId, result, incidentIdAtRequest)
      setLifecycleMessages((current) => ({
        ...current,
        [memoryId]: `${result.message} It will be preserved but excluded from future recall.`,
      }))
      setSupersedeForms((current) => {
        const next = { ...current }
        delete next[memoryId]
        return next
      })
      refreshSelectedIncidentMemories(incidentIdAtRequest)
      startMemoryInspectorRefresh()
    } catch (error) {
      setLifecycleErrors((current) => ({
        ...current,
        [memoryId]: readableError(error),
      }))
    } finally {
      finishLifecyclePending(memoryId, 'supersede')
    }
  }

  const memoryCounts = inspectorMemories.reduce(
    (counts, memory) => ({
      total: counts.total + 1,
      active: counts.active + (memory.status === 'active' ? 1 : 0),
      rejected: counts.rejected + (memory.status === 'rejected' ? 1 : 0),
      superseded:
        counts.superseded + (memory.status === 'superseded' ? 1 : 0),
    }),
    { total: 0, active: 0, rejected: 0, superseded: 0 },
  )
  const activeMemoryOptions = inspectorMemories.filter(
    (memory) => memory.status === 'active',
  )
  const filteredInspectorMemories = inspectorMemories.filter((memory) => {
    const statusMatches =
      inspectorStatusFilter === 'all' || memory.status === inspectorStatusFilter
    const typeMatches =
      inspectorTypeFilter === 'all' || memory.memory_type === inspectorTypeFilter
    return statusMatches && typeMatches
  })
  const demoIncidentCount = incidents.filter(isDemoIncident).length
  const visibleIncidents = showDemoIncidentsOnly
    ? incidents.filter(isDemoIncident)
    : incidents
  const detailTabs: { id: DetailTab; label: string; count: number | null }[] = [
    {
      id: 'recommendation',
      label: 'Recommendation',
      count: agentRecommendation
        ? agentRecommendation.recalled_memories.length
        : null,
    },
    {
      id: 'recall',
      label: 'Recalled memories',
      count: memoryRecall ? memoryRecall.memories.length : null,
    },
    {
      id: 'memory',
      label: 'Save memory',
      count: memories.length > 0 ? memories.length : null,
    },
    { id: 'advanced', label: 'Advanced details', count: null },
  ]

  async function runRecommendationFromSummary() {
    setActiveDetailTab('recommendation')
    await handleMemoryAssistedRecommendation()
  }

  async function runRecallFromSummary() {
    setActiveDetailTab('recall')
    await handleRecallMemories()
  }

  function renderMemoryDetails(memory: Memory) {
    return (
      <>
        {memory.root_cause && (
          <p className="recall-detail">
            <strong>Root cause:</strong> {memory.root_cause}
          </p>
        )}
        {memory.resolution && (
          <p className="recall-detail">
            <strong>Resolution:</strong> {memory.resolution}
          </p>
        )}
      </>
    )
  }

  function renderLinkedIncident(memory: Memory) {
    if (
      !memory.linked_incident_title &&
      !memory.linked_incident_service &&
      !memory.linked_incident_environment
    ) {
      return null
    }
    return (
      <div className="linked-incident">
        <p>
          <strong>Linked incident:</strong>{' '}
          {memory.linked_incident_title ?? 'Untitled incident'}
        </p>
        <p>
          {memory.linked_incident_service ?? 'Unknown service'} ·{' '}
          {memory.linked_incident_environment ?? 'Unknown environment'}
        </p>
      </div>
    )
  }

  function renderSavedMemoryAdvancedDetails(memory: Memory) {
    return renderAdvancedDetails(
      <dl className="advanced-metadata">
        <div>
          <dt>Memory ID</dt>
          <dd>{memory.id}</dd>
        </div>
        {memory.superseded_by && (
          <div>
            <dt>Replacement ID</dt>
            <dd>{memory.superseded_by}</dd>
          </div>
        )}
        <div>
          <dt>Embedding model</dt>
          <dd>{memory.embedding_model_id}</dd>
        </div>
        <div>
          <dt>Embedding dimension</dt>
          <dd>{memory.embedding_dimension}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDate(memory.created_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatDate(memory.updated_at)}</dd>
        </div>
      </dl>,
    )
  }

  function renderRecalledMemoryAdvancedDetails(memory: {
    memory_id: string
    incident_id: string | null
    embedding_model_id: string
    embedding_dimension: number
    cosine_distance: number
    same_service_score: number
    superseded_by?: string | null
  }) {
    return renderAdvancedDetails(
      <dl className="advanced-metadata">
        <div>
          <dt>Memory ID</dt>
          <dd>{memory.memory_id}</dd>
        </div>
        {memory.incident_id && (
          <div>
            <dt>Linked incident ID</dt>
            <dd>{memory.incident_id}</dd>
          </div>
        )}
        {memory.superseded_by && (
          <div>
            <dt>Replacement ID</dt>
            <dd>{memory.superseded_by}</dd>
          </div>
        )}
        <div>
          <dt>Embedding model</dt>
          <dd>{memory.embedding_model_id}</dd>
        </div>
        <div>
          <dt>Embedding dimension</dt>
          <dd>{memory.embedding_dimension}</dd>
        </div>
        <div>
          <dt>Cosine distance</dt>
          <dd>{formatDistance(memory.cosine_distance)}</dd>
        </div>
        <div>
          <dt>Same-service score</dt>
          <dd>{memory.same_service_score}</dd>
        </div>
      </dl>,
    )
  }

  function renderAgentMemoryAdvancedDetails(memory: AgentRecalledMemory) {
    return renderAdvancedDetails(
      <dl className="advanced-metadata">
        <div>
          <dt>Final score</dt>
          <dd>{formatSimilarity(memory.final_score)}</dd>
        </div>
        <div>
          <dt>Similarity</dt>
          <dd>{formatSimilarity(memory.similarity)}</dd>
        </div>
        <div>
          <dt>Reliability</dt>
          <dd>{formatSimilarity(memory.reliability)}</dd>
        </div>
        <div>
          <dt>Successes</dt>
          <dd>{memory.success_count}</dd>
        </div>
        <div>
          <dt>Failures</dt>
          <dd>{memory.failure_count}</dd>
        </div>
      </dl>,
    )
  }

  function renderFeedbackControls(memoryId: string, status: MemoryStatus) {
    const isFeedbackPending = Boolean(feedbackPendingMemoryIds[memoryId])
    const isLifecyclePending = Boolean(lifecyclePendingByMemory[memoryId])
    const disableFeedback = isFeedbackPending || isLifecyclePending || status !== 'active'

    return (
      <div className="feedback-panel">
        <div className="feedback-actions">
          <button
            className="secondary-button feedback-button"
            type="button"
            onClick={() => void handleMemoryFeedback(memoryId, 'success')}
            disabled={disableFeedback}
          >
            {isFeedbackPending ? 'Recording…' : 'Mark successful'}
          </button>
          <button
            className="secondary-button feedback-button"
            type="button"
            onClick={() => void handleMemoryFeedback(memoryId, 'failure')}
            disabled={disableFeedback}
          >
            {isFeedbackPending ? 'Recording…' : 'Mark failed'}
          </button>
        </div>
        {status !== 'active' && (
          <p className="lifecycle-note">
            Feedback is accepted only for active memories.
          </p>
        )}
        {feedbackMessages[memoryId] && (
          <p className="feedback-message">{feedbackMessages[memoryId]}</p>
        )}
        {feedbackErrors[memoryId] && (
          <p className="feedback-message feedback-error" role="alert">
            {feedbackErrors[memoryId]}
          </p>
        )}
      </div>
    )
  }

  function renderLifecycleDetails(memory: {
    superseded_by: string | null
    supersession_reason: string | null
    replacement_memory_summary?: string | null
    replacement_memory_type?: MemoryType | null
    replacement_memory_status?: MemoryStatus | null
  }) {
    if (!memory.superseded_by && !memory.supersession_reason) {
      return null
    }
    return (
      <div className="lifecycle-details">
        {memory.superseded_by && (
          <p>
            <strong>Superseded:</strong>{' '}
            {memory.replacement_memory_summary
              ? 'A better memory replaced this one.'
              : 'Replacement memory recorded.'}
          </p>
        )}
        {memory.replacement_memory_summary && (
          <p>
            <strong>Replacement:</strong>{' '}
            {memory.replacement_memory_type
              ? `${formatMemoryType(memory.replacement_memory_type)} · `
              : ''}
            {memory.replacement_memory_summary} ·{' '}
            {memory.replacement_memory_status ?? 'active'}
          </p>
        )}
        {memory.supersession_reason && (
          <p>
            <strong>Reason:</strong> {memory.supersession_reason}
          </p>
        )}
      </div>
    )
  }

  function renderLifecycleControls(memoryId: string, status: MemoryStatus) {
    const pendingAction = lifecyclePendingByMemory[memoryId]
    const pendingReject = pendingAction === 'reject'
    const pendingSupersede = pendingAction === 'supersede'
    const isFeedbackPending = Boolean(feedbackPendingMemoryIds[memoryId])
    const supersedeState = supersedeForms[memoryId] ?? {
      superseded_by: '',
      reason: '',
    }
    const replacementOptions = activeMemoryOptions.filter(
      (memory) => memory.id !== memoryId,
    )

    if (status !== 'active') {
      return (
        <div className="lifecycle-panel">
          <p className="lifecycle-note">
            This memory is inactive and will not appear in future recall.
          </p>
          {lifecycleMessages[memoryId] && (
            <p className="feedback-message">{lifecycleMessages[memoryId]}</p>
          )}
          {lifecycleErrors[memoryId] && (
            <p className="feedback-message feedback-error" role="alert">
              {lifecycleErrors[memoryId]}
            </p>
          )}
        </div>
      )
    }

    return (
      <div className="lifecycle-panel">
        <p className="lifecycle-note">
          Supersede means a better memory replaces an older one.
        </p>
        <div className="lifecycle-grid">
          <label>
            Reject reason
            <input
              value={rejectReasons[memoryId] ?? ''}
              onChange={(event) =>
                setRejectReason(memoryId, event.target.value)
              }
              maxLength={4000}
              placeholder="Too vague or incorrect"
            />
          </label>
          <button
            className="secondary-button lifecycle-button"
            type="button"
            onClick={() => void handleRejectMemory(memoryId)}
            disabled={Boolean(pendingAction) || isFeedbackPending}
          >
            {pendingReject ? 'Rejecting…' : 'Reject memory'}
          </button>
        </div>

        <div className="lifecycle-grid lifecycle-grid-wide">
          <label>
            Replacement memory
            <select
              value={supersedeState.superseded_by}
              onChange={(event) =>
                updateSupersedeForm(
                  memoryId,
                  'superseded_by',
                  event.target.value,
                )
              }
              disabled={replacementOptions.length === 0}
            >
              <option value="">
                {replacementOptions.length === 0
                  ? 'No other active memories'
                  : 'Select an active memory'}
              </option>
              {replacementOptions.map((memory) => (
                <option key={memory.id} value={memory.id}>
                  {formatReplacementOption(memory)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Supersession reason
            <input
              value={supersedeState.reason}
              onChange={(event) =>
                updateSupersedeForm(memoryId, 'reason', event.target.value)
              }
              maxLength={4000}
              placeholder="Newer resolution replaced this memory"
            />
          </label>
          <button
            className="secondary-button lifecycle-button"
            type="button"
            onClick={() => void handleSupersedeMemory(memoryId)}
            disabled={
              Boolean(pendingAction) ||
              isFeedbackPending ||
              replacementOptions.length === 0
            }
          >
            {pendingSupersede ? 'Superseding…' : 'Supersede memory'}
          </button>
        </div>
        {replacementOptions.length === 0 && (
          <p className="lifecycle-note">
            Create another active memory before superseding this one.
          </p>
        )}

        {lifecycleMessages[memoryId] && (
          <p className="feedback-message">{lifecycleMessages[memoryId]}</p>
        )}
        {lifecycleErrors[memoryId] && (
          <p className="feedback-message feedback-error" role="alert">
            {lifecycleErrors[memoryId]}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div>
          <p className="eyebrow">Incident operations</p>
          <h1>RecallOps</h1>
          <p className="tagline">
            An AI-assisted incident memory system that learns from outcomes.
          </p>
        </div>
        <div className="api-status" aria-live="polite">
          <span className={`status-dot ${listError ? 'status-dot-error' : ''}`} />
          {isLoading
            ? 'Loading incidents…'
            : listError
              ? 'Incident API unavailable'
              : `${incidents.length} incident${incidents.length === 1 ? '' : 's'} loaded`}
        </div>
      </header>

      <main>
        <section className="panel create-panel" aria-labelledby="create-heading">
          <div className="section-heading">
            <p className="section-kicker">New record</p>
            <h2 id="create-heading">Create incident</h2>
          </div>

          <form onSubmit={handleSubmit}>
            <label>
              Title
              <input
                value={form.title}
                onChange={(event) => updateForm('title', event.target.value)}
                maxLength={200}
                placeholder="Checkout latency"
                required
              />
            </label>

            <label>
              Description
              <textarea
                value={form.description}
                onChange={(event) => updateForm('description', event.target.value)}
                placeholder="What is happening?"
                rows={5}
                required
              />
            </label>

            <div className="form-row">
              <label>
                Service
                <input
                  value={form.service}
                  onChange={(event) => updateForm('service', event.target.value)}
                  maxLength={100}
                  placeholder="checkout-api"
                  required
                />
              </label>

              <label>
                Environment
                <select
                  value={form.environment}
                  onChange={(event) =>
                    updateForm(
                      'environment',
                      event.target.value as IncidentEnvironment,
                    )
                  }
                >
                  {environments.map((environment) => (
                    <option key={environment} value={environment}>
                      {environment}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {formError && (
              <p className="message message-error" role="alert">
                {formError}
              </p>
            )}

            <button className="primary-button" type="submit" disabled={isCreating}>
              {isCreating ? 'Creating…' : 'Create incident'}
            </button>
          </form>
        </section>

        <div className="workspace">
          <section className="panel list-panel" aria-labelledby="list-heading">
            <div className="section-heading section-heading-row">
              <div>
                <p className="section-kicker">Live queue</p>
                <h2 id="list-heading">Incidents</h2>
              </div>
              {!isLoading && !listError && (
                <span className="count-badge">{visibleIncidents.length}</span>
              )}
            </div>

            {!isLoading && !listError && demoIncidentCount > 0 && (
              <label className="demo-toggle">
                <input
                  type="checkbox"
                  checked={showDemoIncidentsOnly}
                  onChange={(event) =>
                    setShowDemoIncidentsOnly(event.target.checked)
                  }
                />
                Demo records only
                <span className="demo-toggle-count">{demoIncidentCount}</span>
              </label>
            )}

            {isLoading && <p className="message">Loading incidents…</p>}
            {listError && (
              <p className="message message-error" role="alert">
                {listError}
              </p>
            )}
            {!isLoading && !listError && incidents.length === 0 && (
              <div className="empty-state">
                <h3>No incidents yet</h3>
                <p>Create the first incident to begin the operational record.</p>
              </div>
            )}

            {!isLoading &&
              !listError &&
              incidents.length > 0 &&
              visibleIncidents.length === 0 && (
                <p className="analysis-placeholder">
                  No demo records match this filter.
                </p>
              )}

            <div className="incident-list">
              {visibleIncidents.map((incident) => (
                <button
                  className={`incident-row ${
                    selectedIncident?.id === incident.id ? 'incident-row-selected' : ''
                  }`}
                  type="button"
                  key={incident.id}
                  onClick={() => void handleSelect(incident)}
                  aria-pressed={selectedIncident?.id === incident.id}
                >
                  <span className="incident-row-main">
                    <strong>{incident.title}</strong>
                    <span className="incident-row-service">
                      {incident.service}
                      {isDemoIncident(incident) && (
                        <span className="demo-badge">Demo</span>
                      )}
                    </span>
                  </span>
                  <span className="incident-row-meta">
                    <span className={`status-pill status-${incident.status}`}>
                      {incident.status}
                    </span>
                    <span>{incident.environment}</span>
                    <time dateTime={incident.created_at}>
                      {formatDate(incident.created_at)}
                    </time>
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel detail-panel" aria-labelledby="detail-heading">
            <div className="section-heading">
              <p className="section-kicker">Incident record</p>
              <h2 id="detail-heading">Details</h2>
            </div>

            {!selectedIncident ? (
              <div className="empty-state detail-placeholder">
                <h3>Select an incident</h3>
                <p>Choose an item from the queue to inspect its full context.</p>
              </div>
            ) : (
              <article className="incident-detail">
                <div className="incident-summary-bar">
                  <div className="detail-title-row">
                    <h3>{selectedIncident.title}</h3>
                    <span
                      className={`status-pill status-${selectedIncident.status}`}
                    >
                      {selectedIncident.status}
                    </span>
                  </div>

                  <div className="incident-chips">
                    <span className="incident-chip">
                      {selectedIncident.service}
                    </span>
                    <span className="incident-chip">
                      {selectedIncident.environment}
                    </span>
                    {isDemoIncident(selectedIncident) && (
                      <span className="incident-chip incident-chip-demo">
                        Demo record
                      </span>
                    )}
                  </div>

                  <p className="description">{selectedIncident.description}</p>

                  <div className="incident-actions">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => void runRecommendationFromSummary()}
                      disabled={isRunningAgentRecommendation}
                    >
                      {isRunningAgentRecommendation
                        ? 'Running…'
                        : 'Run memory-assisted recommendation'}
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void runRecallFromSummary()}
                      disabled={isRecallingMemories}
                    >
                      {isRecallingMemories
                        ? 'Recalling…'
                        : 'Recall similar memories'}
                    </button>
                  </div>
                </div>

                {isDetailLoading && <p className="message">Refreshing details…</p>}
                {detailError && (
                  <p className="message message-error" role="alert">
                    {detailError}
                  </p>
                )}

                <div
                  className="detail-tabs"
                  role="tablist"
                  aria-label="Incident detail sections"
                >
                  {detailTabs.map((tab) => (
                    <button
                      key={tab.id}
                      id={`detail-tab-${tab.id}`}
                      className={`detail-tab ${
                        activeDetailTab === tab.id ? 'detail-tab-active' : ''
                      }`}
                      type="button"
                      role="tab"
                      aria-selected={activeDetailTab === tab.id}
                      aria-controls={`detail-panel-${tab.id}`}
                      onClick={() => setActiveDetailTab(tab.id)}
                    >
                      {tab.label}
                      {tab.count !== null && (
                        <span className="detail-tab-count">{tab.count}</span>
                      )}
                    </button>
                  ))}
                </div>

                {activeDetailTab === 'advanced' && (
                <div
                  className="detail-tab-panel"
                  id="detail-panel-advanced"
                  role="tabpanel"
                  aria-labelledby="detail-tab-advanced"
                >
                <dl>
                  <div>
                    <dt>Service</dt>
                    <dd>{selectedIncident.service}</dd>
                  </div>
                  <div>
                    <dt>Environment</dt>
                    <dd>{selectedIncident.environment}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDate(selectedIncident.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatDate(selectedIncident.updated_at)}</dd>
                  </div>
                </dl>

                <section className="analysis-section" aria-labelledby="analysis-heading">
                  <div className="analysis-heading-row">
                    <div>
                      <p className="section-kicker">Incident only</p>
                      <h3 id="analysis-heading">AI analysis</h3>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void handleAnalyze()}
                      disabled={isAnalyzing}
                    >
                      {isAnalyzing ? 'Analyzing…' : 'Analyze incident'}
                    </button>
                  </div>

                  {analysisError && (
                    <p className="message message-error" role="alert">
                      {analysisError}
                    </p>
                  )}

                  {!analysis && !analysisError && !isAnalyzing && (
                    <p className="analysis-placeholder">
                      Generate a structured first-pass analysis from this
                      incident only, without saved memory context.
                    </p>
                  )}

                  {analysis && (
                    <div className="analysis-content">
                      <div className="analysis-summary">
                        <span className="analysis-label">Likely category</span>
                        <strong>{analysis.likely_category}</strong>
                        <p>{analysis.summary}</p>
                      </div>

                      <div className="analysis-grid">
                        <div>
                          <h4>Hypotheses</h4>
                          <ul>
                            {analysis.hypotheses.map((hypothesis) => (
                              <li key={hypothesis}>{hypothesis}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <h4>Recommended next steps</h4>
                          <ol>
                            {analysis.recommended_next_steps.map((step) => (
                              <li key={step}>{step}</li>
                            ))}
                          </ol>
                        </div>
                      </div>

                      <div className="analysis-cautions">
                        <h4>Cautions</h4>
                        {analysis.cautions.length > 0 ? (
                          <ul>
                            {analysis.cautions.map((caution) => (
                              <li key={caution}>{caution}</li>
                            ))}
                          </ul>
                        ) : (
                          <p>No specific cautions returned.</p>
                        )}
                      </div>

                      {renderAdvancedDetails(
                        <dl className="advanced-metadata">
                          <div>
                            <dt>Analysis model</dt>
                            <dd>{analysis.model_id}</dd>
                          </div>
                        </dl>,
                      )}
                    </div>
                  )}
                </section>

                <section
                  className="embedding-section"
                  aria-labelledby="embedding-heading"
                >
                  <div className="analysis-heading-row">
                    <div>
                      <p className="section-kicker">Semantic foundation</p>
                      <h3 id="embedding-heading">Embedding preview</h3>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void handleEmbeddingPreview()}
                      disabled={isEmbedding}
                    >
                      {isEmbedding
                        ? 'Generating…'
                        : 'Generate embedding preview'}
                    </button>
                  </div>

                  {embeddingError && (
                    <p className="message message-error" role="alert">
                      {embeddingError}
                    </p>
                  )}

                  {!embeddingPreview && !embeddingError && !isEmbedding && (
                    <p className="analysis-placeholder">
                      Generate a semantic fingerprint for this incident. The
                      vector itself remains private to the backend.
                    </p>
                  )}

                  {embeddingPreview && (
                    <div className="embedding-content">
                      <p className="success-callout">
                        Semantic fingerprint generated. RecallOps can compare
                        this incident with saved memories without displaying the
                        vector.
                      </p>
                      {renderAdvancedDetails(
                        <>
                          <dl className="advanced-metadata">
                            <div>
                              <dt>Model</dt>
                              <dd>{embeddingPreview.model_id}</dd>
                            </div>
                            <div>
                              <dt>Dimension</dt>
                              <dd>{embeddingPreview.dimension}</dd>
                            </div>
                            <div>
                              <dt>Input tokens</dt>
                              <dd>{embeddingPreview.input_text_token_count}</dd>
                            </div>
                          </dl>
                          <div className="embedding-preview-text">
                            <h4>Deterministic input text</h4>
                            <pre>{embeddingPreview.text_preview}</pre>
                          </div>
                        </>,
                      )}
                      <p className="vector-notice">
                        Vector values are intentionally excluded from this preview.
                      </p>
                    </div>
                  )}
                </section>
                </div>
                )}

                {activeDetailTab === 'recall' && (
                <div
                  className="detail-tab-panel"
                  id="detail-panel-recall"
                  role="tabpanel"
                  aria-labelledby="detail-tab-recall"
                >
                <section className="recall-section" aria-labelledby="recall-heading">
                  <div className="analysis-heading-row">
                    <div>
                      <p className="section-kicker">Semantic recall</p>
                      <h3 id="recall-heading">Recalled memories</h3>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void handleRecallMemories()}
                      disabled={isRecallingMemories}
                    >
                      {isRecallingMemories
                        ? 'Recalling…'
                        : 'Recall similar memories'}
                    </button>
                  </div>

                  {memoryRecallError && (
                    <p className="message message-error" role="alert">
                      {memoryRecallError}
                    </p>
                  )}

                  {!memoryRecall && !memoryRecallError && !isRecallingMemories && (
                    <p className="analysis-placeholder">
                      Search active saved memories using this incident&apos;s
                      semantic embedding.
                    </p>
                  )}

                  {memoryRecall && memoryRecall.memories.length === 0 && (
                    <p className="analysis-placeholder">{memoryRecall.message}</p>
                  )}

                  {memoryRecall && memoryRecall.memories.length > 0 && (
                    <div className="recall-content">
                      <p className="recall-summary">
                        Similarity finds related active memories. Reliability
                        improves when users mark memories successful, then the
                        deterministic ranking orders the results.
                      </p>
                      <p className="recall-summary">
                        Rejected and superseded memories are preserved, but they
                        will not appear in future recall.
                      </p>
                      {renderAdvancedDetails(
                        <dl className="advanced-metadata">
                          <div>
                            <dt>Similarity threshold</dt>
                            <dd>{formatSimilarity(memoryRecall.min_similarity)}</dd>
                          </div>
                          <div>
                            <dt>Query model</dt>
                            <dd>{memoryRecall.query_embedding_model_id}</dd>
                          </div>
                          <div>
                            <dt>Candidates</dt>
                            <dd>{memoryRecall.candidate_count}</dd>
                          </div>
                          <div>
                            <dt>Returned</dt>
                            <dd>{memoryRecall.returned_count}</dd>
                          </div>
                          <div>
                            <dt>Ranking formula</dt>
                            <dd>{memoryRecall.ranking_formula}</dd>
                          </div>
                        </dl>,
                      )}
                      <div className="recall-list">
                        {memoryRecall.memories.map((memory) => (
                          <article
                            className={`recall-row memory-row-${memory.status}`}
                            key={memory.memory_id}
                          >
                            <div className="memory-row-heading">
                              <div className="recall-title-group">
                                <span className="recall-rank">
                                  #{memory.rank}
                                </span>
                                <span className="memory-type">
                                  {formatMemoryType(memory.memory_type)}
                                </span>
                                <span
                                  className={`memory-status status-${memory.status}`}
                                >
                                  {memory.status}
                                </span>
                              </div>
                              <div className="recall-score-group">
                                <span className="recall-score">
                                  {formatSimilarity(memory.final_score)}
                                </span>
                                <span className="recall-score-label">
                                  final score
                                </span>
                              </div>
                            </div>
                            <p>{memory.summary}</p>
                            {memory.root_cause && (
                              <p className="recall-detail">
                                <strong>Root cause:</strong> {memory.root_cause}
                              </p>
                            )}
                            {memory.resolution && (
                              <p className="recall-detail">
                                <strong>Resolution:</strong> {memory.resolution}
                              </p>
                            )}
                            <dl className="recall-metadata">
                              <div>
                                <dt>Similarity</dt>
                                <dd>{formatSimilarity(memory.similarity)}</dd>
                              </div>
                              <div>
                                <dt>Reliability</dt>
                                <dd>{formatSimilarity(memory.reliability)}</dd>
                              </div>
                              <div>
                                <dt>Same service</dt>
                                <dd>{memory.same_service ? 'Yes' : 'No'}</dd>
                              </div>
                              <div>
                                <dt>Successes</dt>
                                <dd>{memory.success_count}</dd>
                              </div>
                              <div>
                                <dt>Failures</dt>
                                <dd>{memory.failure_count}</dd>
                              </div>
                            </dl>
                            <div className="why-recalled-box">
                              <span>Why recalled</span>
                              <p className="recall-explanation">
                                {memory.why_recalled}
                              </p>
                            </div>
                            {renderLifecycleDetails(memory)}
                            {renderRecalledMemoryAdvancedDetails(memory)}
                            {renderFeedbackControls(
                              memory.memory_id,
                              memory.status,
                            )}
                            {renderLifecycleControls(
                              memory.memory_id,
                              memory.status,
                            )}
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                </section>

                </div>
                )}

                {activeDetailTab === 'recommendation' && (
                <div
                  className="detail-tab-panel"
                  id="detail-panel-recommendation"
                  role="tabpanel"
                  aria-labelledby="detail-tab-recommendation"
                >
                <section className="agent-section" aria-labelledby="agent-heading">
                  <div className="analysis-heading-row">
                    <div>
                      <p className="section-kicker">Memory-assisted</p>
                      <h3 id="agent-heading">Recommendation</h3>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void handleMemoryAssistedRecommendation()}
                      disabled={isRunningAgentRecommendation}
                    >
                      {isRunningAgentRecommendation
                        ? 'Running…'
                        : 'Run memory-assisted recommendation'}
                    </button>
                  </div>

                  {agentRecommendationError && (
                    <p className="message message-error" role="alert">
                      {agentRecommendationError}
                    </p>
                  )}

                  {!agentRecommendation &&
                    !agentRecommendationError &&
                    !isRunningAgentRecommendation && (
                      <p className="analysis-placeholder">
                        RecallOps checks active persistent memory before asking
                        Bedrock to recommend next steps.
                      </p>
                    )}

                  {agentRecommendation && (
                    <div className="agent-content">
                      <p
                        className={
                          agentRecommendation.memory_used
                            ? 'success-callout'
                            : 'analysis-placeholder'
                        }
                      >
                        {agentRecommendation.memory_used
                          ? 'RecallOps checked persistent memory before recommending next steps.'
                          : 'No relevant active memories were found; recommendation was generated from the incident only.'}
                      </p>

                      <div className="analysis-summary">
                        <span className="analysis-label">Likely root cause</span>
                        <strong>{agentRecommendation.likely_root_cause}</strong>
                        <p>{agentRecommendation.summary}</p>
                      </div>

                      <div className="analysis-grid">
                        <div>
                          <h4>Memory-grounded findings</h4>
                          <ul>
                            {agentRecommendation.memory_grounded_findings.map(
                              (finding) => (
                                <li key={finding}>{finding}</li>
                              ),
                            )}
                          </ul>
                        </div>
                        <div>
                          <h4>Recommended next steps</h4>
                          <ol>
                            {agentRecommendation.recommended_next_steps.map(
                              (step) => (
                                <li key={step}>{step}</li>
                              ),
                            )}
                          </ol>
                        </div>
                      </div>

                      <div className="analysis-grid">
                        <div className="analysis-cautions">
                          <h4>Cautions</h4>
                          <ul>
                            {agentRecommendation.cautions.map((caution) => (
                              <li key={caution}>{caution}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <h4>Memory influence notes</h4>
                          <ul>
                            {agentRecommendation.memory_influence_notes.map(
                              (note) => (
                                <li key={note}>{note}</li>
                              ),
                            )}
                          </ul>
                        </div>
                      </div>

                      {agentRecommendation.recalled_memories.length > 0 && (
                        <div className="agent-memory-list">
                          <h4>These memories influenced the recommendation</h4>
                          {agentRecommendation.recalled_memories.map((memory) => (
                            <article
                              className={`agent-memory-card memory-row-${memory.status}`}
                              key={`${memory.rank}-${memory.summary}`}
                            >
                              <div className="memory-row-heading">
                                <div className="recall-title-group">
                                  <span className="recall-rank">
                                    #{memory.rank}
                                  </span>
                                  <span className="memory-type">
                                    {formatMemoryType(memory.memory_type)}
                                  </span>
                                  <span
                                    className={`memory-status status-${memory.status}`}
                                  >
                                    {memory.status}
                                  </span>
                                </div>
                              </div>
                              <p>{memory.summary}</p>
                              {memory.root_cause && (
                                <p className="recall-detail">
                                  <strong>Root cause:</strong>{' '}
                                  {memory.root_cause}
                                </p>
                              )}
                              {memory.resolution && (
                                <p className="recall-detail">
                                  <strong>Resolution:</strong>{' '}
                                  {memory.resolution}
                                </p>
                              )}
                              <div className="why-recalled-box">
                                <span>Why this memory mattered</span>
                                <p className="recall-explanation">
                                  {memory.why_recalled}
                                </p>
                              </div>
                              {renderAgentMemoryAdvancedDetails(memory)}
                            </article>
                          ))}
                        </div>
                      )}

                      {renderAdvancedDetails(
                        <dl className="advanced-metadata">
                          <div>
                            <dt>Recommendation model</dt>
                            <dd>{agentRecommendation.model_id}</dd>
                          </div>
                          <div>
                            <dt>Memories used</dt>
                            <dd>{agentRecommendation.recalled_memory_count}</dd>
                          </div>
                        </dl>,
                      )}
                    </div>
                  )}
                </section>

                </div>
                )}

                {activeDetailTab === 'memory' && (
                <div
                  className="detail-tab-panel"
                  id="detail-panel-memory"
                  role="tabpanel"
                  aria-labelledby="detail-tab-memory"
                >
                <section className="memory-section" aria-labelledby="memory-heading">
                  <div className="analysis-heading-row">
                    <div>
                      <p className="section-kicker">Long-term memory</p>
                      <h3 id="memory-heading">Save as memory</h3>
                    </div>
                    {isMemoryListLoading && (
                      <span className="memory-loading">Refreshing…</span>
                    )}
                  </div>

                  <form className="memory-form" onSubmit={handleCreateMemory}>
                    <div className="memory-form-grid">
                      <label>
                        Type
                        <select
                          value={memoryForm.memory_type}
                          onChange={(event) =>
                            updateMemoryForm(
                              'memory_type',
                              event.target.value as MemoryType,
                            )
                          }
                        >
                          {memoryTypes.map((type) => (
                            <option key={type} value={type}>
                              {formatMemoryType(type)}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label>
                        Summary
                        <textarea
                          value={memoryForm.summary}
                          onChange={(event) =>
                            updateMemoryForm('summary', event.target.value)
                          }
                          placeholder="What should RecallOps remember from this incident?"
                          rows={3}
                          maxLength={4000}
                          required
                        />
                      </label>

                      <label>
                        Root cause
                        <textarea
                          value={memoryForm.root_cause}
                          onChange={(event) =>
                            updateMemoryForm('root_cause', event.target.value)
                          }
                          rows={3}
                          maxLength={4000}
                        />
                      </label>

                      <label>
                        Resolution
                        <textarea
                          value={memoryForm.resolution}
                          onChange={(event) =>
                            updateMemoryForm('resolution', event.target.value)
                          }
                          rows={3}
                          maxLength={4000}
                        />
                      </label>
                    </div>

                    {memoryFormError && (
                      <p className="message message-error" role="alert">
                        {memoryFormError}
                      </p>
                    )}

                    <button
                      className="secondary-button memory-submit"
                      type="submit"
                      disabled={isSavingMemory}
                    >
                      {isSavingMemory ? 'Saving…' : 'Save memory'}
                    </button>
                  </form>

                  {memoryListError && (
                    <p className="message message-error" role="alert">
                      {memoryListError}
                    </p>
                  )}

                  {!isMemoryListLoading && !memoryListError && memories.length === 0 && (
                    <p className="analysis-placeholder">
                      No saved memories for this incident yet.
                    </p>
                  )}

                  {memories.length > 0 && (
                    <div className="memory-list">
                      {memories.map((memory) => (
                        <article
                          className={`memory-row memory-row-${memory.status}`}
                          key={memory.id}
                        >
                          <div className="memory-row-heading">
                            <span className="memory-type">
                              {formatMemoryType(memory.memory_type)}
                            </span>
                            <span className={`memory-status status-${memory.status}`}>
                              {memory.status}
                            </span>
                          </div>
                          <p>{memory.summary}</p>
                          {renderMemoryDetails(memory)}
                          {renderLinkedIncident(memory)}
                          <dl className="memory-metadata">
                            <div>
                              <dt>Successes</dt>
                              <dd>{memory.success_count}</dd>
                            </div>
                            <div>
                              <dt>Failures</dt>
                              <dd>{memory.failure_count}</dd>
                            </div>
                            <div>
                              <dt>Reliability</dt>
                              <dd>{formatSimilarity(memory.reliability)}</dd>
                            </div>
                          </dl>
                          {renderLifecycleDetails(memory)}
                          {renderSavedMemoryAdvancedDetails(memory)}
                          {renderFeedbackControls(memory.id, memory.status)}
                          {renderLifecycleControls(memory.id, memory.status)}
                        </article>
                      ))}
                    </div>
                  )}
                </section>
                </div>
                )}
              </article>
            )}
          </section>
        </div>

        <section
          className="panel memory-inspector-panel"
          aria-labelledby="memory-inspector-heading"
        >
          <div className="analysis-heading-row">
            <div>
              <p className="section-kicker">Memory Inspector</p>
              <h2 id="memory-inspector-heading">Saved memories</h2>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={startMemoryInspectorRefresh}
              disabled={isInspectorLoading}
            >
              {isInspectorLoading ? 'Refreshing…' : 'Refresh memories'}
            </button>
          </div>

          <p className="recall-summary">
            Active memories can be recalled and improved with feedback. Rejected
            and superseded memories are preserved for history, but excluded from
            future recall.
          </p>

          <dl className="memory-inspector-counts">
            <div>
              <dt>Total</dt>
              <dd>{memoryCounts.total}</dd>
            </div>
            <div>
              <dt>Active</dt>
              <dd>{memoryCounts.active}</dd>
            </div>
            <div>
              <dt>Rejected</dt>
              <dd>{memoryCounts.rejected}</dd>
            </div>
            <div>
              <dt>Superseded</dt>
              <dd>{memoryCounts.superseded}</dd>
            </div>
          </dl>

          <div className="inspector-filters">
            <label>
              Status
              <select
                value={inspectorStatusFilter}
                onChange={(event) =>
                  setInspectorStatusFilter(
                    event.target.value as InspectorStatusFilter,
                  )
                }
              >
                <option value="all">all</option>
                <option value="active">active</option>
                <option value="rejected">rejected</option>
                <option value="superseded">superseded</option>
              </select>
            </label>

            <label>
              Type
              <select
                value={inspectorTypeFilter}
                onChange={(event) =>
                  setInspectorTypeFilter(
                    event.target.value as InspectorMemoryTypeFilter,
                  )
                }
              >
                <option value="all">all</option>
                {memoryTypes.map((type) => (
                  <option key={type} value={type}>
                    {formatMemoryType(type)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {inspectorError && (
            <p className="message message-error" role="alert">
              {inspectorError}
            </p>
          )}

          {!isInspectorLoading &&
            !inspectorError &&
            filteredInspectorMemories.length === 0 && (
              <p className="analysis-placeholder">
                No memories match the current inspector filters.
              </p>
            )}

          {filteredInspectorMemories.length > 0 && (
            <div className="memory-list memory-inspector-list">
              {filteredInspectorMemories.map((memory) => (
                <article
                  className={`memory-row memory-row-${memory.status}`}
                  key={memory.id}
                >
                  <div className="memory-row-heading">
                    <span className="memory-type">
                      {formatMemoryType(memory.memory_type)}
                    </span>
                    <span className={`memory-status status-${memory.status}`}>
                      {memory.status}
                    </span>
                  </div>

                  <p>{memory.summary}</p>
                  {renderMemoryDetails(memory)}
                  {renderLinkedIncident(memory)}

                  <dl className="memory-metadata inspector-memory-metadata">
                    <div>
                      <dt>Successes</dt>
                      <dd>{memory.success_count}</dd>
                    </div>
                    <div>
                      <dt>Failures</dt>
                      <dd>{memory.failure_count}</dd>
                    </div>
                    <div>
                      <dt>Reliability</dt>
                      <dd>{formatSimilarity(memory.reliability)}</dd>
                    </div>
                  </dl>

                  {renderLifecycleDetails(memory)}
                  {memory.status !== 'active' && (
                    <p className="lifecycle-note">
                      This memory is inactive and will not appear in future
                      recall.
                    </p>
                  )}
                  {renderSavedMemoryAdvancedDetails(memory)}
                  {renderFeedbackControls(memory.id, memory.status)}
                  {renderLifecycleControls(memory.id, memory.status)}
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
