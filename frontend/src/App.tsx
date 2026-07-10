import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  analyzeIncident,
  createIncident,
  generateEmbeddingPreview,
  getIncident,
  listIncidents,
  type Incident,
  type IncidentAnalysis,
  type IncidentCreateInput,
  type IncidentEmbeddingPreview,
  type IncidentEnvironment,
} from './api/incidents'

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
  const [embeddingPreview, setEmbeddingPreview] =
    useState<IncidentEmbeddingPreview | null>(null)
  const [embeddingError, setEmbeddingError] = useState<string | null>(null)
  const [isEmbedding, setIsEmbedding] = useState(false)
  const detailRequestId = useRef(0)
  const analysisRequestId = useRef(0)
  const embeddingRequestId = useRef(0)

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

  function updateForm<K extends keyof IncidentCreateInput>(
    field: K,
    value: IncidentCreateInput[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }))
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
      embeddingRequestId.current += 1
      setSelectedIncident(created)
      setListError(null)
      setDetailError(null)
      setAnalysis(null)
      setAnalysisError(null)
      setIsAnalyzing(false)
      setEmbeddingPreview(null)
      setEmbeddingError(null)
      setIsEmbedding(false)
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
    embeddingRequestId.current += 1
    setSelectedIncident(incident)
    setIsDetailLoading(true)
    setDetailError(null)
    setAnalysis(null)
    setAnalysisError(null)
    setIsAnalyzing(false)
    setEmbeddingPreview(null)
    setEmbeddingError(null)
    setIsEmbedding(false)

    try {
      const detail = await getIncident(incident.id)
      if (detailRequestId.current === requestId) {
        setSelectedIncident(detail)
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

  return (
    <div className="app-shell">
      <header className="site-header">
        <div>
          <p className="eyebrow">Incident operations</p>
          <h1>RecallOps</h1>
          <p className="tagline">
            An incident-response agent that learns from outcomes.
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
                <span className="count-badge">{incidents.length}</span>
              )}
            </div>

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

            <div className="incident-list">
              {incidents.map((incident) => (
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
                    <span>{incident.service}</span>
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
                <div className="detail-title-row">
                  <h3>{selectedIncident.title}</h3>
                  <span className={`status-pill status-${selectedIncident.status}`}>
                    {selectedIncident.status}
                  </span>
                </div>

                {isDetailLoading && <p className="message">Refreshing details…</p>}
                {detailError && (
                  <p className="message message-error" role="alert">
                    {detailError}
                  </p>
                )}

                <p className="description">{selectedIncident.description}</p>

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
                      <p className="section-kicker">On-demand</p>
                      <h3 id="analysis-heading">AI analysis</h3>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void handleAnalyze()}
                      disabled={isAnalyzing}
                    >
                      {isAnalyzing ? 'Analyzing…' : 'Analyze with AI'}
                    </button>
                  </div>

                  {analysisError && (
                    <p className="message message-error" role="alert">
                      {analysisError}
                    </p>
                  )}

                  {!analysis && !analysisError && !isAnalyzing && (
                    <p className="analysis-placeholder">
                      Generate a structured first-pass analysis for this incident.
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

                      <p className="model-id">Model: {analysis.model_id}</p>
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
                      Generate metadata for the incident&apos;s semantic embedding.
                      The vector itself remains private to the backend.
                    </p>
                  )}

                  {embeddingPreview && (
                    <div className="embedding-content">
                      <dl className="embedding-metadata">
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
                      <p className="vector-notice">
                        Vector values are intentionally excluded from this preview.
                      </p>
                    </div>
                  )}
                </section>
              </article>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
